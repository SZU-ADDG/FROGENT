#!/usr/bin/env python3
"""Sanitize copied third-party sources without exposing sensitive values."""

from __future__ import annotations

import argparse
import ast
import io
import os
import re
import stat
import tempfile
import tokenize
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


EXPECTED_ROOT = Path("/Users/dongxu/projects/FROGENT")
ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_SIZE = 10 * 1024 * 1024

SOURCE_CONFIG = {
    "frogent": {
        "root": ROOT / "sources" / "frogent",
        "prefix": "FROGENT",
        "token_env": "FROGENT_LLM_API_KEY",
        "credential_uri_env": "FROGENT_CREDENTIAL_URI",
    },
    "mcp": {
        "root": ROOT / "sources" / "mcp",
        "prefix": "MCP",
        "token_env": "MCP_TEST_LLM_API_KEY",
        "credential_uri_env": "MCP_CREDENTIAL_URI",
    },
    "trioworkspace": {
        "root": ROOT / "sources" / "trioworkspace",
        "prefix": "TRIOWORKSPACE",
        "token_env": "TRIOWORKSPACE_API_KEY",
        "credential_uri_env": "TRIOWORKSPACE_CREDENTIAL_URI",
    },
}

LOCKFILE_IP_EXCLUSIONS = {"uv.lock"}

IPV4_RE = re.compile(r"(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])")
TOKEN_RE = re.compile(
    r"(?:"
    r"sk-[A-Za-z0-9._-]{16,}"
    r"|(?:AKIA|ASIA)[A-Z0-9]{16}"
    r"|gh[pousr]_[A-Za-z0-9]{30,}"
    r"|github_pat_[A-Za-z0-9_]{30,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|hf_[A-Za-z0-9]{20,}"
    r")"
)
CREDENTIAL_URI_RE = re.compile(
    r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@[^\s'\"]+"
)
PRIVATE_KEY_BLOCK_RE = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----.*?"
    r"-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----",
    re.DOTALL,
)
STRING_START_RE = re.compile(
    r"(?is)^(?P<prefix>[rubf]*)(?P<quote>'''|\"\"\"|'|\")"
)
OS_IMPORT_RE = re.compile(
    r"(?m)^[ \t]*(?:import[ \t]+[^#\r\n]*\bos\b|from[ \t]+os[ \t]+import\b)"
)

SSH_ASSIGN_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<name>ssh_host|ssh_user|ssh_password)"
    r"(?P<spacing>[ \t]*=[ \t]*)(?P<prefix>[rubfRUBF]*)"
    r"(?P<quote>['\"])(?P<value>.*?)(?P=quote)"
    r"(?P<suffix>[ \t]*(?:#.*)?)$"
)
SSH_CALL_RE = re.compile(
    r"ssh_scp_files\([ \t]*(?P<q1>['\"])[^'\"\r\n]*(?P=q1)[ \t]*,[ \t]*"
    r"(?P<q2>['\"])[^'\"\r\n]*(?P=q2)[ \t]*,[ \t]*"
    r"(?P<q3>['\"])[^'\"\r\n]*(?P=q3)[ \t]*,[ \t]*"
)
CONFIG_ASSIGN_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<name>SECRET_KEY|QWEN_API_KEY|SQLALCHEMY_DATABASE_URI)"
    r"[ \t]*=.*$"
)
PYMYSQL_ARG_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<name>host|user|password|database|unix_socket)"
    r"[ \t]*=[ \t]*(?P<quote>['\"])(?P<value>.*?)(?P=quote)"
    r"(?P<suffix>[ \t]*,?[ \t]*(?:#.*)?)$"
)
HARDCODED_ASSIGN_RE = re.compile(
    r"(?im)^[ \t]*(?P<name>(?:[A-Za-z_][A-Za-z0-9_]*_)?"
    r"(?:password|passwd|secret(?:_key)?|api_key|access_key|auth_token))"
    r"[ \t]*(?::[^=\r\n]+)?=[ \t]*(?P<quote>['\"])(?P<value>[^'\"\r\n]+)"
    r"(?P=quote)"
)
HARDCODED_DICT_RE = re.compile(
    r"(?i)(?P<keyq>['\"])(?P<name>password|passwd|secret(?:_key)?|api_key|access_key|auth_token|"
    r"jsessionid|sl-session|session(?:_id|_token|_cookie)?|cookies?)"
    r"(?P=keyq)[ \t]*:[ \t]*(?P<valq>['\"])(?P<value>[^'\"\r\n]+)"
    r"(?P=valq)"
)
PUBMED_EMAIL_RE = re.compile(
    r"(?i)\bPubMed[ \t]*\([^\r\n)]*\bemail[ \t]*=[ \t]*"
    r"(?P<quote>['\"])(?P<value>[^'\"\r\n]+)(?P=quote)"
)
FRONTEND_CREDENTIAL_LOG_RE = re.compile(
    r"(?i)\bconsole\.(?:log|debug|info|warn|error)[ \t]*\("
    r"[^)\r\n]*(?:password|passwd|confirmPassword)"
)

SSH_ENV = {
    "ssh_host": "FROGENT_SSH_HOST",
    "ssh_user": "FROGENT_SSH_USER",
    "ssh_password": "FROGENT_SSH_PASSWORD",
}
CONFIG_ENV = {
    "SECRET_KEY": "SECRET_KEY",
    "QWEN_API_KEY": "QWEN_API_KEY",
    "SQLALCHEMY_DATABASE_URI": "FROGENT_DATABASE_URI",
}
PYMYSQL_ENV = {
    "host": "FROGENT_DB_HOST",
    "user": "FROGENT_DB_USER",
    "password": "FROGENT_DB_PASSWORD",
    "database": "FROGENT_DB_NAME",
    "unix_socket": "FROGENT_DB_UNIX_SOCKET",
}


class SanitizationError(RuntimeError):
    """Raised when a safety invariant is violated."""


@dataclass
class FileResult:
    path: Path
    original: str
    transformed: str
    bom: bool
    rules: Counter[str] = field(default_factory=Counter)
    env_names: set[str] = field(default_factory=set)

    @property
    def changed(self) -> bool:
        return self.original != self.transformed


def assert_root() -> None:
    if ROOT != EXPECTED_ROOT.resolve():
        raise SanitizationError("project root guard failed")
    if not (ROOT / "AGENTS.md").is_file():
        raise SanitizationError("AGENTS.md guard failed")


def assert_safe_path(path: Path) -> None:
    resolved = path.resolve(strict=False)
    if resolved != ROOT and ROOT not in resolved.parents:
        raise SanitizationError("path escaped the project root")
    relative = path.relative_to(ROOT)
    current = ROOT
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise SanitizationError("symbolic links are not allowed in imported sources")


def is_private_host(value: str) -> bool:
    try:
        parts = tuple(int(part) for part in value.split("."))
    except ValueError:
        return False
    if len(parts) != 4 or any(part < 0 or part > 255 for part in parts):
        return False
    return (
        parts[0] == 10
        or (parts[0] == 172 and 16 <= parts[1] <= 31)
        or (parts[0] == 192 and parts[1] == 168)
    )


def private_matches(text: str) -> list[re.Match[str]]:
    return [match for match in IPV4_RE.finditer(text) if is_private_host(match.group(0))]


def placeholder(env_name: str) -> str:
    return "$" + "{" + env_name + "}"


def decode_text(path: Path) -> tuple[str, bool] | None:
    data = path.read_bytes()
    if b"\x00" in data:
        return None
    bom = data.startswith(b"\xef\xbb\xbf")
    if bom:
        data = data[3:]
    try:
        return data.decode("utf-8"), bom
    except UnicodeDecodeError:
        return None


def iter_text_files(source_root: Path) -> list[tuple[Path, str, bool]]:
    assert_safe_path(source_root)
    if not source_root.is_dir():
        raise SanitizationError("expected source directory is missing")
    results: list[tuple[Path, str, bool]] = []
    for path in sorted(source_root.rglob("*"), key=lambda item: item.as_posix()):
        assert_safe_path(path)
        if path.is_symlink():
            raise SanitizationError("symbolic links are not allowed in imported sources")
        if not path.is_file() or path.stat().st_size > MAX_FILE_SIZE:
            continue
        decoded = decode_text(path)
        if decoded is not None:
            results.append((path, decoded[0], decoded[1]))
    return results


def build_private_env_maps(
    source_files: dict[str, list[tuple[Path, str, bool]]]
) -> dict[str, dict[str, str]]:
    mappings: dict[str, dict[str, str]] = {}
    for source_name, files in source_files.items():
        values: set[str] = set()
        for path, text, _ in files:
            if path.name in LOCKFILE_IP_EXCLUSIONS:
                continue
            values.update(match.group(0) for match in private_matches(text))
        ordered = sorted(values, key=lambda value: tuple(int(part) for part in value.split(".")))
        prefix = str(SOURCE_CONFIG[source_name]["prefix"])
        mappings[source_name] = {
            value: f"{prefix}_PRIVATE_HOST_{index:02d}"
            for index, value in enumerate(ordered, start=1)
        }
    return mappings


def split_line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n") or line.endswith("\r"):
        return line[:-1], line[-1]
    return line, ""


def transform_targeted_lines(
    path: Path, text: str, rules: Counter[str], env_names: set[str]
) -> str:
    relative = path.relative_to(ROOT).as_posix()
    output: list[str] = []
    for line in text.splitlines(keepends=True):
        body, ending = split_line_ending(line)
        updated = body

        ssh_match = SSH_ASSIGN_RE.match(updated)
        if ssh_match:
            env_name = SSH_ENV[ssh_match.group("name")]
            candidate = (
                ssh_match.group("indent")
                + ssh_match.group("name")
                + ssh_match.group("spacing")
                + f'os.getenv("{env_name}", "")'
                + ssh_match.group("suffix")
            )
            if candidate != updated:
                updated = candidate
                rules["ssh_assignment"] += 1
                env_names.add(env_name)

        if relative == "sources/frogent/config.py":
            config_match = CONFIG_ASSIGN_RE.match(updated)
            if config_match:
                env_name = CONFIG_ENV[config_match.group("name")]
                candidate = (
                    config_match.group("indent")
                    + config_match.group("name")
                    + f' = os.getenv("{env_name}", "")'
                )
                if candidate != updated:
                    updated = candidate
                    rules["application_config"] += 1
                    env_names.add(env_name)

        if relative == "sources/frogent/test_pymysql.py":
            mysql_match = PYMYSQL_ARG_RE.match(updated)
            if mysql_match:
                env_name = PYMYSQL_ENV[mysql_match.group("name")]
                candidate = (
                    mysql_match.group("indent")
                    + mysql_match.group("name")
                    + f'=os.getenv("{env_name}", "")'
                    + mysql_match.group("suffix")
                )
                if candidate != updated:
                    updated = candidate
                    rules["database_argument"] += 1
                    env_names.add(env_name)

        output.append(updated + ending)
    return "".join(output)


def transform_ssh_calls(
    text: str, rules: Counter[str], env_names: set[str]
) -> tuple[str, bool]:
    runtime_replacement = (
        'ssh_scp_files(os.getenv("FROGENT_SSH_HOST", ""), '
        'os.getenv("FROGENT_SSH_USER", ""), '
        'os.getenv("FROGENT_SSH_PASSWORD", ""), '
    )
    comment_replacement = (
        "ssh_scp_files(<FROGENT_SSH_HOST>, <FROGENT_SSH_USER>, "
        "<FROGENT_SSH_PASSWORD>, "
    )
    used_runtime = False

    def replace(match: re.Match[str]) -> str:
        nonlocal used_runtime
        rules["ssh_call"] += 1
        env_names.update(
            {"FROGENT_SSH_HOST", "FROGENT_SSH_USER", "FROGENT_SSH_PASSWORD"}
        )
        line_start = text.rfind("\n", 0, match.start()) + 1
        if text[line_start : match.start()].lstrip().startswith("#"):
            return comment_replacement
        used_runtime = True
        return runtime_replacement

    return SSH_CALL_RE.sub(replace, text), used_runtime


def line_offsets(text: str) -> list[int]:
    offsets = [0]
    total = 0
    for line in text.splitlines(keepends=True):
        total += len(line)
        offsets.append(total)
    if not text or (text and text[-1] not in "\r\n"):
        offsets.append(len(text))
    return offsets


def absolute_offset(offsets: list[int], position: tuple[int, int]) -> int:
    row, column = position
    return offsets[row - 1] + column


def string_expression(
    value: str,
    ip_map: dict[str, str],
    token_env: str,
    credential_uri_env: str,
) -> tuple[str | None, Counter[str], set[str]]:
    matches: list[tuple[int, int, str, str, str]] = []
    for match in TOKEN_RE.finditer(value):
        matches.append((match.start(), match.end(), "provider_token", token_env, ""))
    for match in CREDENTIAL_URI_RE.finditer(value):
        matches.append(
            (
                match.start(),
                match.end(),
                "credential_uri",
                credential_uri_env,
                "",
            )
        )
    for match in private_matches(value):
        env_name = ip_map.get(match.group(0))
        if env_name:
            matches.append(
                (match.start(), match.end(), "private_host", env_name, "127.0.0.1")
            )
    if not matches:
        return None, Counter(), set()

    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    accepted: list[tuple[int, int, str, str, str]] = []
    cursor = -1
    for item in matches:
        if item[0] >= cursor:
            accepted.append(item)
            cursor = item[1]

    pieces: list[str] = []
    rules: Counter[str] = Counter()
    env_names: set[str] = set()
    cursor = 0
    for start, end, rule, env_name, fallback in accepted:
        if start > cursor:
            pieces.append(repr(value[cursor:start]))
        pieces.append(f'os.getenv("{env_name}", {fallback!r})')
        rules[rule] += 1
        env_names.add(env_name)
        cursor = end
    if cursor < len(value):
        pieces.append(repr(value[cursor:]))
    return "(" + " + ".join(pieces) + ")", rules, env_names


def replace_documentation_values(
    value: str,
    ip_map: dict[str, str],
    token_env: str,
    credential_uri_env: str,
) -> tuple[str, Counter[str], set[str]]:
    rules: Counter[str] = Counter()
    env_names: set[str] = set()

    def replace_token(match: re.Match[str]) -> str:
        rules["provider_token"] += 1
        env_names.add(token_env)
        return placeholder(token_env)

    def replace_uri(match: re.Match[str]) -> str:
        rules["credential_uri"] += 1
        env_names.add(credential_uri_env)
        return placeholder(credential_uri_env)

    def replace_ip(match: re.Match[str]) -> str:
        value = match.group(0)
        if not is_private_host(value) or value not in ip_map:
            return value
        env_name = ip_map[value]
        rules["private_host"] += 1
        env_names.add(env_name)
        return placeholder(env_name)

    updated = TOKEN_RE.sub(replace_token, value)
    updated = CREDENTIAL_URI_RE.sub(replace_uri, updated)
    updated = IPV4_RE.sub(replace_ip, updated)
    return updated, rules, env_names


def transform_python_tokens(
    text: str,
    ip_map: dict[str, str],
    token_env: str,
    credential_uri_env: str,
) -> tuple[str, Counter[str], set[str], bool]:
    offsets = line_offsets(text)
    replacements: list[tuple[int, int, str]] = []
    rules: Counter[str] = Counter()
    env_names: set[str] = set()
    needs_os = False

    generator = tokenize.generate_tokens(io.StringIO(text).readline)
    while True:
        try:
            token = next(generator)
        except StopIteration:
            break
        except (tokenize.TokenError, IndentationError):
            break

        if token.type == tokenize.COMMENT:
            updated, token_rules, token_env_names = replace_documentation_values(
                token.string, ip_map, token_env, credential_uri_env
            )
            if updated != token.string:
                replacements.append(
                    (
                        absolute_offset(offsets, token.start),
                        absolute_offset(offsets, token.end),
                        updated,
                    )
                )
                rules.update(token_rules)
                env_names.update(token_env_names)
            continue

        if token.type != tokenize.STRING:
            continue
        string_match = STRING_START_RE.match(token.string)
        if not string_match:
            continue
        prefix = string_match.group("prefix").lower()
        quote = string_match.group("quote")

        if len(quote) == 3:
            updated, token_rules, token_env_names = replace_documentation_values(
                token.string, ip_map, token_env, credential_uri_env
            )
            if updated != token.string:
                replacements.append(
                    (
                        absolute_offset(offsets, token.start),
                        absolute_offset(offsets, token.end),
                        updated,
                    )
                )
                rules.update(token_rules)
                env_names.update(token_env_names)
            continue

        if "f" in prefix:
            updated = token.string
            token_rules: Counter[str] = Counter()
            token_env_names: set[str] = set()
            inner_quote = "'" if quote == '"' else '"'

            def f_token(match: re.Match[str]) -> str:
                token_rules["provider_token"] += 1
                token_env_names.add(token_env)
                return "{os.getenv(" + inner_quote + token_env + inner_quote + ", " + inner_quote + inner_quote + ")}"

            def f_uri(match: re.Match[str]) -> str:
                token_rules["credential_uri"] += 1
                token_env_names.add(credential_uri_env)
                return "{os.getenv(" + inner_quote + credential_uri_env + inner_quote + ", " + inner_quote + inner_quote + ")}"

            def f_ip(match: re.Match[str]) -> str:
                raw = match.group(0)
                if not is_private_host(raw) or raw not in ip_map:
                    return raw
                env_name = ip_map[raw]
                token_rules["private_host"] += 1
                token_env_names.add(env_name)
                return (
                    "{os.getenv("
                    + inner_quote
                    + env_name
                    + inner_quote
                    + ", "
                    + inner_quote
                    + "127.0.0.1"
                    + inner_quote
                    + ")}"
                )

            updated = TOKEN_RE.sub(f_token, updated)
            updated = CREDENTIAL_URI_RE.sub(f_uri, updated)
            updated = IPV4_RE.sub(f_ip, updated)
            if updated != token.string:
                replacements.append(
                    (
                        absolute_offset(offsets, token.start),
                        absolute_offset(offsets, token.end),
                        updated,
                    )
                )
                rules.update(token_rules)
                env_names.update(token_env_names)
                needs_os = True
            continue

        try:
            value = ast.literal_eval(token.string)
        except (SyntaxError, ValueError):
            continue
        if not isinstance(value, str):
            continue
        expression, token_rules, token_env_names = string_expression(
            value, ip_map, token_env, credential_uri_env
        )
        if expression is None:
            continue
        replacements.append(
            (
                absolute_offset(offsets, token.start),
                absolute_offset(offsets, token.end),
                expression,
            )
        )
        rules.update(token_rules)
        env_names.update(token_env_names)
        needs_os = True

    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, rules, env_names, needs_os


def ensure_import_os(text: str) -> tuple[str, bool]:
    if OS_IMPORT_RE.search(text):
        return text, False
    newline = "\r\n" if text.count("\r\n") > text.count("\n") / 2 else "\n"
    lines = text.splitlines(keepends=True)
    insertion = 0
    if lines and lines[0].startswith("#!"):
        insertion = 1
    if insertion < len(lines) and re.search(r"coding[:=][ \t]*[-\w.]+", lines[insertion]):
        insertion += 1

    try:
        generator = tokenize.generate_tokens(io.StringIO(text).readline)
        first_significant: tokenize.TokenInfo | None = None
        for token in generator:
            if token.type in {
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.COMMENT,
                tokenize.ENCODING,
            }:
                continue
            first_significant = token
            break
        if (
            first_significant is not None
            and first_significant.type == tokenize.STRING
            and first_significant.start[1] == 0
        ):
            insertion = max(insertion, first_significant.end[0])
    except (tokenize.TokenError, IndentationError):
        pass

    scan = insertion
    while scan < len(lines):
        stripped = lines[scan].strip()
        if not stripped or stripped.startswith("#"):
            scan += 1
            continue
        if stripped.startswith("from __future__ import "):
            insertion = scan + 1
            scan += 1
            continue
        break

    lines.insert(insertion, "import os" + newline)
    return "".join(lines), True


def transform_non_python(
    text: str,
    ip_map: dict[str, str],
    source_prefix: str,
    token_env: str,
    credential_uri_env: str,
    skip_private_hosts: bool,
) -> tuple[str, Counter[str], set[str]]:
    updated, rules, env_names = replace_documentation_values(
        text,
        {} if skip_private_hosts else ip_map,
        token_env,
        credential_uri_env,
    )

    def documented_env(name: str) -> str:
        normalized = name.lower()
        if "api_key" in normalized or "auth_token" in normalized:
            return token_env
        if "secret_key" in normalized and source_prefix == "FROGENT":
            return "SECRET_KEY"
        if "password" in normalized or "passwd" in normalized:
            return f"{source_prefix}_DOCUMENTED_PASSWORD"
        if "access_key" in normalized:
            return f"{source_prefix}_DOCUMENTED_ACCESS_KEY"
        return f"{source_prefix}_DOCUMENTED_SECRET"

    def replace_documented_literal(match: re.Match[str]) -> str:
        if benign_literal(match.group("value")):
            return match.group(0)
        env_name = documented_env(match.group("name"))
        relative_start = match.start("value") - match.start()
        relative_end = match.end("value") - match.start()
        rules["documented_secret"] += 1
        env_names.add(env_name)
        return (
            match.group(0)[:relative_start]
            + placeholder(env_name)
            + match.group(0)[relative_end:]
        )

    updated = HARDCODED_ASSIGN_RE.sub(replace_documented_literal, updated)
    updated = HARDCODED_DICT_RE.sub(replace_documented_literal, updated)
    return updated, rules, env_names


def sanitize_file(
    path: Path,
    text: str,
    bom: bool,
    source_name: str,
    ip_map: dict[str, str],
) -> FileResult:
    config = SOURCE_CONFIG[source_name]
    rules: Counter[str] = Counter()
    env_names: set[str] = set()
    transformed = text

    private_key_count = len(PRIVATE_KEY_BLOCK_RE.findall(transformed))
    if private_key_count:
        transformed = PRIVATE_KEY_BLOCK_RE.sub("<redacted-private-key>", transformed)
        rules["private_key"] += private_key_count

    needs_os = False
    if path.suffix.lower() == ".py":
        transformed = transform_targeted_lines(path, transformed, rules, env_names)
        transformed, ssh_needs_os = transform_ssh_calls(transformed, rules, env_names)
        needs_os = needs_os or ssh_needs_os
        transformed, token_rules, token_env_names, token_needs_os = transform_python_tokens(
            transformed,
            ip_map,
            str(config["token_env"]),
            str(config["credential_uri_env"]),
        )
        rules.update(token_rules)
        env_names.update(token_env_names)
        needs_os = needs_os or token_needs_os or any(
            rules[rule_name]
            for rule_name in (
                "ssh_assignment",
                "application_config",
                "database_argument",
            )
        )
        if needs_os:
            transformed, inserted = ensure_import_os(transformed)
            if inserted:
                rules["os_import"] += 1
    else:
        transformed, text_rules, text_env_names = transform_non_python(
            transformed,
            ip_map,
            str(config["prefix"]),
            str(config["token_env"]),
            str(config["credential_uri_env"]),
            path.name in LOCKFILE_IP_EXCLUSIONS,
        )
        rules.update(text_rules)
        env_names.update(text_env_names)

    return FileResult(path, text, transformed, bom, rules, env_names)


def benign_literal(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        not normalized
        or normalized.startswith("<")
        or normalized.startswith("${")
        or normalized.startswith(("your-", "your_", "replace-", "replace_"))
        or any(
            marker in normalized
            for marker in ("redacted", "placeholder", "dummy", "example")
        )
        or normalized
        in {
            "changeme",
            "change-me",
            "empty",
            "none",
            "null",
        }
    )


def scan_residual(path: Path, text: str) -> set[str]:
    findings: set[str] = set()
    if TOKEN_RE.search(text):
        findings.add("provider_token")
    if CREDENTIAL_URI_RE.search(text):
        findings.add("credential_uri")
    if PRIVATE_KEY_BLOCK_RE.search(text):
        findings.add("private_key")
    if path.name not in LOCKFILE_IP_EXCLUSIONS and private_matches(text):
        findings.add("private_host")
    for pattern in (HARDCODED_ASSIGN_RE, HARDCODED_DICT_RE):
        for match in pattern.finditer(text):
            if not benign_literal(match.group("value")):
                findings.add("literal_secret_assignment")
                break
    for match in PUBMED_EMAIL_RE.finditer(text):
        if not benign_literal(match.group("value")):
            findings.add("literal_pubmed_email")
            break
    if FRONTEND_CREDENTIAL_LOG_RE.search(text):
        findings.add("frontend_credential_log")
    if SSH_CALL_RE.search(text):
        findings.add("literal_ssh_call")
    return findings


def atomic_write(result: FileResult) -> None:
    assert_safe_path(result.path)
    original_stat = result.path.stat()
    payload = result.transformed.encode("utf-8")
    if result.bom:
        payload = b"\xef\xbb\xbf" + payload
    fd, temporary_name = tempfile.mkstemp(
        prefix=".sanitize-", suffix=".tmp", dir=result.path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, stat.S_IMODE(original_stat.st_mode))
        os.replace(temporary_path, result.path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sanitize copied source trees without printing sensitive values."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="preview and validate only")
    mode.add_argument("--apply", action="store_true", help="apply local sanitization")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    assert_root()

    source_files = {
        name: iter_text_files(Path(config["root"]))
        for name, config in SOURCE_CONFIG.items()
    }
    private_env_maps = build_private_env_maps(source_files)

    results: list[FileResult] = []
    for source_name, files in source_files.items():
        for path, text, bom in files:
            results.append(
                sanitize_file(
                    path,
                    text,
                    bom,
                    source_name,
                    private_env_maps[source_name],
                )
            )

    changed = [result for result in results if result.changed]
    residual: dict[str, set[str]] = {}
    for result in results:
        findings = scan_residual(result.path, result.transformed)
        if findings:
            residual[result.path.relative_to(ROOT).as_posix()] = findings

    aggregate_rules: Counter[str] = Counter()
    env_names: set[str] = set()
    for result in changed:
        aggregate_rules.update(result.rules)
        env_names.update(result.env_names)

    print("mode=" + ("apply" if args.apply else "check"))
    print(f"text_files_scanned={len(results)}")
    print(f"files_to_change={len(changed)}")
    for rule, count in sorted(aggregate_rules.items()):
        print(f"rule.{rule}={count}")
    for result in sorted(changed, key=lambda item: item.path.as_posix()):
        labels = ",".join(sorted(result.rules))
        print(f"change={result.path.relative_to(ROOT).as_posix()} rules={labels}")
    for env_name in sorted(env_names):
        print(f"env={env_name}")
    print(f"residual_files={len(residual)}")
    for relative, findings in sorted(residual.items()):
        print(f"residual={relative} types={','.join(sorted(findings))}")

    if residual:
        return 2
    if args.apply:
        for result in changed:
            atomic_write(result)
        print(f"files_changed={len(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
