#!/usr/bin/env python3
"""Poll TrioMol2 tasks and stream verified artifacts on the TrioWorkspace server."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO
from urllib.error import HTTPError
from urllib.request import Request, urlopen


CONTROL_URL = "http://127.0.0.1:4471"
SECRET_PATH = Path("/work/doomx/TrioWorkspace/runtime/control-plane/secrets/control-plane-secret")
ALLOWED_OUTPUT_ROOT = Path("/work/doomx/FROGENT/runtime")
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,63}$")
TERMINAL_STATES = {"succeeded", "failed", "cancelled"}
CHUNK_BYTES = 1024 * 1024
DEFAULT_MAX_ARTIFACT_BYTES = 1024 * 1024 * 1024


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def safe_id(value: object, name: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ValueError(f"{name} is invalid")
    return value


def safe_filename(value: object) -> str:
    filename = re.sub(r"[^A-Za-z0-9._-]", "_", str(value or "artifact"))[:160]
    if filename in {"", ".", ".."}:
        raise ValueError("artifact filename is invalid")
    return filename


def validate_output_root(path: Path) -> Path:
    allowed = Path(os.path.abspath(ALLOWED_OUTPUT_ROOT))
    absolute = Path(os.path.abspath(path))
    try:
        relative = absolute.relative_to(allowed)
    except ValueError as error:
        raise ValueError("output root must be contained in the FROGENT runtime root") from error
    if not relative.parts:
        raise ValueError("output root must be strictly contained in the FROGENT runtime root")
    candidate = allowed
    for part in relative.parts:
        candidate /= part
        if candidate.exists() and candidate.is_symlink():
            raise ValueError("output root contains a symbolic link")
    resolved_allowed = allowed.resolve(strict=True)
    resolved = absolute.resolve(strict=False)
    if resolved_allowed not in resolved.parents:
        raise ValueError("output root must be strictly contained in the FROGENT runtime root")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def signed_headers(method: str, path: str, body: bytes, user_id: str, email: str) -> dict[str, str]:
    secret = SECRET_PATH.read_bytes().strip()
    if len(secret) < 32:
        raise RuntimeError("control-plane secret is invalid")
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


def open_get(path: str, user_id: str, email: str) -> BinaryIO:
    request = Request(
        CONTROL_URL + path,
        headers=signed_headers("GET", path, b"", user_id, email),
        method="GET",
    )
    try:
        return urlopen(request)
    except HTTPError as error:
        detail = error.read(4096).decode("utf-8", errors="replace")
        raise RuntimeError(f"control-plane GET returned HTTP {error.code}: {detail}") from error


def get_task(task_id: str, user_id: str, email: str) -> dict[str, Any]:
    with open_get(f"/v1/tasks/{task_id}", user_id, email) as response:
        payload = response.read(2 * 1024 * 1024 + 1)
    if len(payload) > 2 * 1024 * 1024:
        raise RuntimeError("task metadata exceeded 2 MiB")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise RuntimeError("task metadata is malformed")
    return value


def verify_existing(target: Path, expected_size: int, expected_sha256: str) -> bool:
    if not target.exists():
        return False
    digest = hashlib.sha256()
    size = 0
    with target.open("rb") as handle:
        while chunk := handle.read(CHUNK_BYTES):
            size += len(chunk)
            digest.update(chunk)
    if size != expected_size or digest.hexdigest() != expected_sha256:
        raise RuntimeError(f"existing artifact conflicts with metadata: {target}")
    return True


def download_artifact(
    *,
    output_root: Path,
    task_id: str,
    artifact: dict[str, Any],
    user_id: str,
    email: str,
    max_artifact_bytes: int,
) -> dict[str, Any]:
    artifact_id = safe_id(artifact.get("id"), "artifact id")
    expected_size = artifact.get("byteSize")
    expected_sha256 = artifact.get("sha256")
    if (
        isinstance(expected_size, bool)
        or not isinstance(expected_size, int)
        or not 0 <= expected_size <= max_artifact_bytes
    ):
        raise RuntimeError("artifact size is invalid or exceeds the server-side limit")
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise RuntimeError("artifact checksum is invalid")

    directory = output_root / "artifacts" / task_id / artifact_id
    directory.mkdir(parents=True, exist_ok=True)
    if any(path.is_symlink() for path in (output_root, output_root / "artifacts", directory.parent, directory)):
        raise RuntimeError("artifact path contains a symbolic link")
    target = (directory / safe_filename(artifact.get("filename"))).resolve(strict=False)
    if output_root not in target.parents:
        raise RuntimeError("artifact path escaped the output root")
    if verify_existing(target, expected_size, expected_sha256):
        return {"artifact_id": artifact_id, "path": str(target), "status": "verified_existing"}

    temporary = target.with_suffix(target.suffix + ".part")
    if temporary.exists():
        temporary.unlink()
    digest = hashlib.sha256()
    size = 0
    path = f"/v1/tasks/{task_id}/artifacts/{artifact_id}"
    try:
        with open_get(path, user_id, email) as response, temporary.open("xb") as handle:
            while chunk := response.read(CHUNK_BYTES):
                size += len(chunk)
                if size > max_artifact_bytes:
                    raise RuntimeError("artifact response exceeded the server-side limit")
                digest.update(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if size != expected_size or digest.hexdigest() != expected_sha256:
            raise RuntimeError("downloaded artifact failed size or checksum verification")
        os.replace(temporary, target)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise
    return {"artifact_id": artifact_id, "path": str(target), "status": "downloaded"}


def poll(args: argparse.Namespace) -> dict[str, Any]:
    submissions = load_json(args.submissions)
    records: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    download_failures = 0
    for submitted in submissions["tasks"]:
        task_id = safe_id(submitted["task"]["id"], "task id")
        task = get_task(task_id, args.user_id, args.user_email)
        state = str(task.get("status") or task.get("state") or "unknown")
        counts[state] = counts.get(state, 0) + 1
        downloads: list[dict[str, Any]] = []
        for artifact in task.get("artifacts") or []:
            try:
                result = download_artifact(
                    output_root=args.output_root,
                    task_id=task_id,
                    artifact=artifact,
                    user_id=args.user_id,
                    email=args.user_email,
                    max_artifact_bytes=args.max_artifact_bytes,
                )
                downloads.append({**result, "error": None})
            except Exception as error:  # Preserve other artifacts and the exact failure boundary.
                download_failures += 1
                downloads.append(
                    {
                        "artifact_id": artifact.get("id"),
                        "path": None,
                        "status": "failed",
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
        records.append(
            {
                "task_name": submitted["task_name"],
                "pdb_id": submitted.get("pdb_id") or submitted.get("case", {}).get("pdb_id"),
                "seed": submitted.get("seed"),
                "task_id": task_id,
                "state": state,
                "latest_event": task.get("latestEvent"),
                "artifacts": task.get("artifacts") or [],
                "downloads": downloads,
            }
        )
        print(f"{submitted['task_name']}\t{state}\t{len(downloads)} artifacts", flush=True)

    snapshot = {
        "schema_version": "frogent-triomol2-server-status-v1",
        "updated_at": now(),
        "counts": counts,
        "download_failures": download_failures,
        "all_terminal": all(item["state"] in TERMINAL_STATES for item in records),
        "tasks": records,
    }
    save_json(args.output_root / "status.json", snapshot)
    return snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submissions", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--interval-seconds", type=int, default=900)
    parser.add_argument("--max-artifact-bytes", type=int, default=DEFAULT_MAX_ARTIFACT_BYTES)
    parser.add_argument("--user-id", default="frogent-mcp")
    parser.add_argument("--user-email", default="frogent-mcp@localhost.invalid")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.interval_seconds <= 0 or args.max_artifact_bytes <= 0:
        parser.error("interval and artifact limits must be positive")
    args.submissions = args.submissions.resolve(strict=True)
    args.output_root = validate_output_root(args.output_root)
    return args


def main() -> int:
    args = parse_args()
    while True:
        snapshot = poll(args)
        print(
            json.dumps(
                {
                    "counts": snapshot["counts"],
                    "download_failures": snapshot["download_failures"],
                    "status_path": str(args.output_root / "status.json"),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        if args.once or snapshot["all_terminal"]:
            return 0 if snapshot["download_failures"] == 0 else 1
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(130)
