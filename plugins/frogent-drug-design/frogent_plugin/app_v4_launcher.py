"""Contained loader that wires the read-only app_v4 source to ResearchService."""

import importlib
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from uuid import uuid4

from .app_v4_bridge import AppV4ResearchManager
from .research_factory import RuntimeConfig, build_research_service


@dataclass(frozen=True, slots=True)
class AppV4LaunchConfig:
    plugin_root: Path
    source_root: Path
    runtime_root: Path
    secret_key: str
    database_uri: str
    memory_path: Path

    @classmethod
    def from_env(cls, plugin_root: Path, source_root: Path):
        plugin, source = plugin_root.resolve(), source_root.resolve()
        _validate_source(source, plugin)
        runtime = plugin / ".runtime" / "app-v4"
        secret = os.getenv("SECRET_KEY", "").strip()
        if not secret:
            raise ValueError("SECRET_KEY must be non-empty")
        memory = _runtime_path(os.getenv("FROGENT_MEMORY_DB", ""), runtime,
                               "research-memory.sqlite3")
        database = os.getenv("FROGENT_DATABASE_URI", "").strip()
        database = database or "sqlite:///" + str(runtime / "app-v4.sqlite3")
        _validate_database(database, runtime)
        return cls(plugin, source, runtime, secret, database, memory)


def create_app_v4_research(config: AppV4LaunchConfig, *, service=None, models_module=None,
                           runner=None, _runtime_boundary: Path | None = None):
    plugin = config.plugin_root.resolve()
    runtime = _contained_runtime(config.runtime_root, plugin, _runtime_boundary)
    source = config.source_root.resolve()
    _validate_source(source, plugin)
    if not (source / "app_v4.py").is_file():
        raise ValueError("source root must contain app_v4.py")
    uploads = _directory(runtime / "uploads", runtime)
    _directory(runtime / "static", runtime)
    memory = _contained_file(config.memory_path, runtime)
    _validate_database(config.database_uri, runtime)
    if not config.secret_key.strip():
        raise ValueError("SECRET_KEY must be non-empty")
    app_module = _load_source_app(source, runtime, config, models_module)
    app = app_module.app
    app.config.update(SECRET_KEY=config.secret_key, UPLOAD_FOLDER=str(uploads),
        SOURCE_TEMPLATE_PATH=str(source / "templates" / "index.html"),
        ASSET_FOLDER=str(source / "assets"), FROGENT_MEMORY_DB=str(memory))
    app.static_folder = str(uploads)
    runtime_config = _runtime_config(plugin, memory) if service is None else None
    research = service or build_research_service(runtime_config, runner=runner)
    manager = AppV4ResearchManager(research, _conversation_getter(), uploads)
    app_module.assistant_manager = manager
    _install_routes(app, app_module, source)
    with app.app_context():
        app_module.db.create_all()
    return app


def _load_source_app(source: Path, runtime: Path, config: AppV4LaunchConfig, models_module):
    qam, configuration = ModuleType("QAM_v4"), ModuleType("config")
    qam.QwenAssistantManager = _PlaceholderManager
    configuration.Config = type("Config", (), {"SECRET_KEY": config.secret_key,
        "SQLALCHEMY_DATABASE_URI": config.database_uri, "SQLALCHEMY_TRACK_MODIFICATIONS": False})
    replacements = {"QAM_v4": qam, "config": configuration}
    if models_module is not None:
        replacements["models"] = models_module
    managed = ("QAM_v4", "config", "models")
    previous = {name: sys.modules.get(name) for name in managed}
    old_cwd, old_path, old_bytecode = Path.cwd(), tuple(sys.path), sys.dont_write_bytecode
    name = "frogent_source_app_v4_" + uuid4().hex
    try:
        sys.modules.update(replacements)
        if models_module is None:
            sys.modules.pop("models", None)
        sys.path.insert(0, str(source))
        sys.dont_write_bytecode = True
        os.chdir(runtime)
        spec = importlib.util.spec_from_file_location(name, source / "app_v4.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load app_v4 source")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        module.__dict__["print"] = _discard_source_print
        return module
    finally:
        os.chdir(old_cwd)
        sys.path[:] = old_path
        sys.dont_write_bytecode = old_bytecode
        sys.modules.pop(name, None)
        for module_name, value in previous.items():
            if value is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = value


def _install_routes(app, source_module, source: Path) -> None:
    flask = importlib.import_module("flask")
    original = app.view_functions["chat"]

    def chat_with_context():
        response = original()
        if getattr(response, "is_streamed", False):
            response.response = flask.stream_with_context(response.response)
        return response

    def index():
        return (source / "templates" / "index.html").read_text(encoding="utf-8")

    def assets(filename):
        return flask.send_from_directory(source / "assets", filename)

    app.view_functions["chat"] = chat_with_context
    app.view_functions["index"] = index
    app.add_url_rule("/assets/<path:filename>", "frogent_assets", assets)


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


class _PlaceholderManager:
    def __init__(self, *args, **kwargs) -> None: pass


def _discard_source_print(*args, **kwargs) -> None:
    """Keep legacy user/chat payloads out of process stdout."""


def _validate_source(source: Path, plugin: Path) -> None:
    expected = plugin.parents[1] / "sources" / "frogent"
    if source != expected.resolve() or not (source / "app_v4.py").is_file():
        raise ValueError("source root must be the read-only sources/frogent directory")


def _contained_runtime(value: Path, plugin: Path, test_boundary: Path | None = None) -> Path:
    result = value.resolve(strict=False)
    if test_boundary is not None:
        boundary = test_boundary.resolve(strict=False)
        boundary.relative_to(plugin)
        result.relative_to(boundary)
        return _directory(result, boundary)
    try:
        relative = result.relative_to(plugin)
    except ValueError as exc:
        raise ValueError("app_v4 runtime must stay inside plugin root") from exc
    if relative.parts[:2] != (".runtime", "app-v4"):
        raise ValueError("app_v4 runtime must be under .runtime/app-v4")
    return _directory(result, plugin)


def _runtime_config(plugin: Path, memory: Path) -> RuntimeConfig:
    previous = os.environ.get("FROGENT_MEMORY_DB")
    try:
        os.environ["FROGENT_MEMORY_DB"] = str(memory)
        return RuntimeConfig.from_env(plugin)
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
        raise ValueError("runtime file must stay under .runtime/app-v4") from exc
    result.parent.mkdir(parents=True, exist_ok=True)
    return result


def _runtime_path(raw: str, runtime: Path, fallback: str) -> Path:
    value = Path(raw.strip()) if raw.strip() else runtime / fallback
    if value.is_absolute():
        return value
    if value.parts[:2] == (".runtime", "app-v4"):
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
