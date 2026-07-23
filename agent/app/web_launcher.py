"""Build the maintained FROGENT web application inside the project runtime."""

import importlib
import os
from dataclasses import dataclass
from pathlib import Path

from agent.app.research_factory import RuntimeConfig, build_research_service
from agent.app.web_bridge import WebResearchManager


@dataclass(frozen=True, slots=True)
class WebLaunchConfig:
    project_root: Path
    runtime_root: Path
    secret_key: str
    database_uri: str
    memory_path: Path

    @classmethod
    def from_env(cls, project_root: Path):
        project = project_root.resolve()
        runtime = project / "runtime" / "app"
        secret = os.getenv("SECRET_KEY", "").strip()
        if not secret:
            raise ValueError("SECRET_KEY must be non-empty")
        memory = _runtime_path(
            os.getenv("FROGENT_MEMORY_DB", ""), runtime, "research-memory.sqlite3"
        )
        database = os.getenv("FROGENT_DATABASE_URI", "").strip()
        database = database or "sqlite:///" + str(runtime / "app.sqlite3")
        _validate_database(database, runtime)
        return cls(project, runtime, secret, database, memory)


def create_web_app(
    config: WebLaunchConfig,
    *,
    service=None,
    models_module=None,
    runner=None,
    _runtime_boundary: Path | None = None,
):
    project = config.project_root.resolve()
    runtime = _contained_runtime(config.runtime_root, project, _runtime_boundary)
    app_root = project / "app"
    if not (app_root / "server.py").is_file():
        raise ValueError("project app directory must contain server.py")
    uploads = _directory(runtime / "uploads", runtime)
    memory = _contained_file(config.memory_path, runtime)
    _validate_database(config.database_uri, runtime)
    if not config.secret_key.strip():
        raise ValueError("SECRET_KEY must be non-empty")
    runtime_config = _runtime_config(project, memory) if service is None else None
    research = service or build_research_service(runtime_config, runner=runner)
    manager = WebResearchManager(research, _conversation_getter(), uploads)
    server = importlib.import_module("app.server")
    return server.build_app(
        secret_key=config.secret_key,
        database_uri=config.database_uri,
        upload_root=uploads,
        manager=manager,
        models_module=models_module,
    )


def _conversation_getter():
    def get(expected_user_id: str) -> str:
        flask = importlib.import_module("flask")
        session_user = flask.session.get("user_id")
        if not isinstance(session_user, str) or session_user != expected_user_id:
            raise PermissionError("stream session user does not match the requested user")
        payload = flask.request.get_json(silent=True) or {}
        chat_id = payload.get("chat_id")
        if not isinstance(chat_id, str) or not chat_id.strip():
            raise ValueError("chat_id must be non-empty text")
        return chat_id.strip()

    return get


def _contained_runtime(
    value: Path, project: Path, test_boundary: Path | None = None
) -> Path:
    result = value.resolve(strict=False)
    if test_boundary is not None:
        boundary = test_boundary.resolve(strict=False)
        boundary.relative_to(project)
        result.relative_to(boundary)
        return _directory(result, boundary)
    try:
        relative = result.relative_to(project)
    except ValueError as exc:
        raise ValueError("web runtime must stay inside project root") from exc
    if relative.parts[:2] != ("runtime", "app"):
        raise ValueError("web runtime must be under runtime/app")
    return _directory(result, project)


def _runtime_config(project: Path, memory: Path) -> RuntimeConfig:
    previous = os.environ.get("FROGENT_MEMORY_DB")
    try:
        os.environ["FROGENT_MEMORY_DB"] = str(memory)
        return RuntimeConfig.from_env(project)
    finally:
        if previous is None:
            os.environ.pop("FROGENT_MEMORY_DB", None)
        else:
            os.environ["FROGENT_MEMORY_DB"] = previous


def _directory(value: Path, boundary: Path) -> Path:
    _reject_symlinks(value, boundary)
    value.mkdir(parents=True, exist_ok=True)
    result = value.resolve()
    result.relative_to(boundary.resolve())
    return result


def _contained_file(value: Path, runtime: Path) -> Path:
    _reject_symlinks(value, runtime)
    result = value.resolve(strict=False)
    try:
        result.relative_to(runtime.resolve())
    except ValueError as exc:
        raise ValueError("runtime file must stay under runtime/app") from exc
    result.parent.mkdir(parents=True, exist_ok=True)
    return result


def _runtime_path(raw: str, runtime: Path, fallback: str) -> Path:
    value = Path(raw.strip()) if raw.strip() else runtime / fallback
    if value.is_absolute():
        return value
    if value.parts[:2] == ("runtime", "app"):
        return runtime.parents[1] / value
    return runtime / value


def _validate_database(uri: str, runtime: Path) -> None:
    if not uri.strip():
        raise ValueError("database URI must be non-empty")
    if uri.startswith("sqlite:///"):
        path = Path(uri.removeprefix("sqlite:///"))
        _contained_file(path if path.is_absolute() else runtime / path, runtime)


def _reject_symlinks(value: Path, boundary: Path) -> None:
    current = value
    while current != boundary.parent and current != current.parent:
        if current.is_symlink():
            raise ValueError("runtime paths cannot traverse symlinks")
        current = current.parent
