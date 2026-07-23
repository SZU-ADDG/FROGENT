"""One-shot remote relay; executed through SSH without persisting remote files."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path("/work/doomx/TrioWorkspace")
SECRET_PATH = ROOT / "runtime/control-plane/secrets/control-plane-secret"
CONTROL_URL = "http://127.0.0.1:4471"
MAX_REQUEST_JSON = 61 * 1024 * 1024
MAX_BODY = 45 * 1024 * 1024
SAFE_TASK = re.compile(r"^/v1/tasks(?:/[a-z0-9][a-z0-9-]{7,63}(?:/artifacts/[a-z0-9-]+)?)?$")


def fail(message: str, code: int = 1) -> None:
    print(json.dumps({"relay_error": message}, separators=(",", ":")))
    raise SystemExit(code)


def load_request() -> dict[str, object]:
    payload = sys.stdin.buffer.read(MAX_REQUEST_JSON + 1)
    if not payload or len(payload) > MAX_REQUEST_JSON:
        fail("relay request is missing or too large")
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail("relay request is malformed")
    if not isinstance(value, dict):
        fail("relay request must be an object")
    return value


def text(value: object, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        fail(f"relay {name} is invalid")
    if any(ord(character) < 32 for character in value):
        fail(f"relay {name} is invalid")
    return value


def request_parts(value: dict[str, object]) -> tuple[str, str, bytes, str, str, str, int]:
    method = text(value.get("method"), "method", 8).upper()
    path = text(value.get("path"), "path", 180)
    if method not in {"GET", "POST"}:
        fail("relay method is unsupported")
    if path != "/healthz" and not SAFE_TASK.fullmatch(path):
        fail("relay path is unsupported")
    encoded = value.get("body_base64", "")
    if not isinstance(encoded, str):
        fail("relay body is invalid")
    try:
        body = base64.b64decode(encoded, validate=True)
    except ValueError:
        fail("relay body is invalid")
    if len(body) > MAX_BODY or (method == "GET" and body):
        fail("relay body is unsupported")
    content_type = text(value.get("content_type", "application/octet-stream"), "content type", 240)
    user_id = text(value.get("user_id"), "user id", 180)
    email = text(value.get("user_email"), "user email", 254)
    maximum = value.get("max_response_bytes")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 0 < maximum <= MAX_BODY:
        fail("relay response limit is invalid")
    return method, path, body, content_type, user_id, email, maximum


def signed_headers(method: str, path: str, body: bytes, user_id: str, email: str) -> dict[str, str]:
    try:
        secret = SECRET_PATH.read_bytes().strip()
    except OSError:
        fail("remote control-plane secret is unavailable")
    if len(secret) < 32:
        fail("remote control-plane secret is invalid")
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(24)
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join([method, path, user_id, email, timestamp, nonce, body_hash]).encode()
    signature = base64.urlsafe_b64encode(hmac.new(secret, canonical, hashlib.sha256).digest())
    return {
        "x-trio-user-id": user_id,
        "x-trio-user-email": email,
        "x-trio-timestamp": timestamp,
        "x-trio-nonce": nonce,
        "x-trio-body-sha256": body_hash,
        "x-trio-signature": signature.rstrip(b"=").decode(),
    }


def read_response(response: object, maximum: int) -> bytes:
    length = getattr(response, "headers").get("content-length")
    if length and length.isdigit() and int(length) > maximum:
        fail("remote response exceeds the configured limit")
    payload = getattr(response, "read")(maximum + 1)
    if len(payload) > maximum:
        fail("remote response exceeds the configured limit")
    return payload


def main() -> None:
    method, path, body, content_type, user_id, email, maximum = request_parts(load_request())
    headers = signed_headers(method, path, body, user_id, email)
    if method == "POST":
        headers["content-type"] = content_type
        headers["content-length"] = str(len(body))
    request = Request(CONTROL_URL + path, data=body if method == "POST" else None, headers=headers, method=method)
    try:
        response = urlopen(request)
        status = response.status
        payload = read_response(response, maximum)
        response_headers = response.headers
    except HTTPError as error:
        status = error.code
        payload = read_response(error, maximum)
        response_headers = error.headers
    except OSError:
        fail("remote control plane is unavailable")
    result = {
        "status": status,
        "content_type": response_headers.get("content-type", "application/octet-stream"),
        "content_disposition": response_headers.get("content-disposition", ""),
        "etag": response_headers.get("etag", ""),
        "body_base64": base64.b64encode(payload).decode(),
    }
    sys.stdout.write(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    main()
