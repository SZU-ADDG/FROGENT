import hashlib
import io
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from agent.app.web_bridge import WebResearchManager
from agent.app.web_launcher import WebLaunchConfig, create_web_app


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT
APP_ROOT = PROJECT / "app"


class _Query:
    def __init__(self, records, filters=None):
        self.records, self.filters = records, filters or {}

    def filter_by(self, **values):
        return _Query(self.records, {**self.filters, **values})

    def first(self):
        return next(iter(self.all()), None)

    def all(self):
        return [item for item in self.records
                if all(getattr(item, key) == value for key, value in self.filters.items())]


class _QueryProperty:
    def __get__(self, instance, owner):
        return _Query(owner.records)


class _Session:
    def add(self, item):
        records = type(item).records
        if item not in records:
            item.id = len(records) + 1
            records.append(item)

    def commit(self): pass
    def rollback(self): pass


class _DB:
    session = _Session()

    def init_app(self, app): self.app = app
    def create_all(self): pass


def _models():
    module = types.ModuleType("models")
    db = _DB()

    class User:
        records = []
        query = _QueryProperty()

        def __init__(self, username): self.username = username
        def set_salt(self, password, email):
            self.password_hash, self.email = password, email
            self.user_id = "user-" + self.username
        def check_password(self, password): return password == self.password_hash
        def get_user_id(self): return self.user_id

    class ChatHistory:
        records = []
        query = _QueryProperty()

        def __init__(self, user_id, conversation_id, title, message_data):
            self.user_id, self.conversation_id = user_id, conversation_id
            self.title, self.message_data = title, message_data
            self.created_at = self.updated_at = datetime(2026, 7, 17)

        @classmethod
        def create(cls, **values):
            item = cls(**values)
            db.session.add(item)
            return item.id

        @classmethod
        def get_by_conversation_id(cls, user_id, conversation_id):
            return cls.query.filter_by(
                user_id=user_id, conversation_id=conversation_id
            ).first()

        def update(self, new_message_data=None, new_title=None):
            self.message_data = new_message_data or self.message_data
            self.title = new_title or self.title
            return True

        def to_dict(self):
            return {"id": self.id, "user_id": self.user_id,
                    "conversation_id": self.conversation_id, "title": self.title,
                    "created_at": self.created_at.isoformat(),
                    "updated_at": self.updated_at.isoformat(),
                    "message_data": self.message_data}

    class ChatFiles:
        records = []
        query = _QueryProperty()

        def __init__(self, **values):
            self.__dict__.update(values)
            self.created_at = self.updated_at = datetime(2026, 7, 17)

        @classmethod
        def create(cls, **values):
            item = cls(**values)
            db.session.add(item)
            return item.id

        @classmethod
        def get_by_conversation_id(cls, user_id, conversation_id):
            return cls.query.filter_by(
                user_id=user_id, conversation_id=conversation_id, is_clear=False
            ).all()

        @classmethod
        def get_by_id(cls, file_id):
            return cls.query.filter_by(id=file_id).first()

        def to_dict(self): return dict(self.__dict__)

        def update(self, is_clear=None, is_visible=None):
            if is_clear is not None and not isinstance(is_clear, bool):
                raise ValueError("is_clear must be boolean")
            if is_visible is not None and not isinstance(is_visible, bool):
                raise ValueError("is_visible must be boolean")
            if is_clear is not None:
                self.is_clear = is_clear
            if is_visible is not None:
                self.is_visible = is_visible
            return True

    module.db, module.User = db, User
    module.ChatHistory, module.ChatFiles = ChatHistory, ChatFiles
    return module


class _Service:
    def __init__(self): self.calls = []

    def stream_payload(self, user_id, payload, *, history=()):
        self.calls.append((user_id, payload, tuple(history)))
        yield 'data: {"content":"source-backed answer","name":"research"}\n\n'
        yield 'data: {"stop":true}\n\n'
        yield "data: [DONE]\n\n"


def _app_identity():
    return {str(path.relative_to(APP_ROOT)): (path.stat().st_size, path.stat().st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest())
            for path in APP_ROOT.rglob("*") if path.is_file()}


class WebAppTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("flask"), "Flask web dependency is optional")
    def test_routes_stream_research_and_save_history_without_app_writes(self):
        before, cwd, prior_models = _app_identity(), Path.cwd(), sys.modules.get("models")
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            runtime = Path(directory)
            upload = runtime / "uploads" / "paper.txt"
            upload.parent.mkdir()
            upload.write_text("attachment", encoding="utf-8")
            structure = runtime / "uploads" / "candidate.pdb"
            structure.write_text("ATOM      1  C   LIG A   1       0.000   0.000   0.000\n", encoding="utf-8")
            config = WebLaunchConfig(ROOT, runtime, "test-secret",
                "sqlite:///" + str(runtime / "app.sqlite3"), runtime / "memory.sqlite3")
            models, service = _models(), _Service()
            app = create_web_app(config, service=service, models_module=models,
                                         _runtime_boundary=runtime)
            self.assertEqual(Path.cwd(), cwd)
            self.assertIs(sys.modules.get("models"), prior_models)
            app.config.update(TESTING=True)
            client = app.test_client()
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertTrue(client.post("/api/register", json={"username": "alice",
                    "password": "pw", "email": "a@example.test"}).get_json()["success"])
                self.assertTrue(client.post("/api/login", json={"username": "alice",
                    "password": "pw"}).get_json()["success"])
                response = client.post("/api/chat", json={"chat_id": "chat-1",
                    "message": "Assess LRRK2", "files": [{"filename": "paper.txt",
                    "path": str(upload), "is_molecular": False, "format": "txt"},
                    {"filename": "candidate.pdb", "path": str(structure),
                    "is_molecular": True, "format": "pdb"}]}, buffered=True)
            self.assertEqual("", stdout.getvalue())
            body = response.get_data(as_text=True)
            self.assertIn('"content":"source-backed answer"', body)
            self.assertIn('"stop":true', body)
            self.assertIn("data: [DONE]", body)
            restored = client.post(
                "/api/chat_history",
                json={"user_id": "user-alice", "chat_id": "chat-1"},
            ).get_json()["chat_session"]
            self.assertEqual(["paper.txt"], [item["filename"] for item in restored["files"]])
            self.assertNotIn("path", restored["files"][0])
            self.assertEqual(["candidate.pdb"], [item["filename"] for item in restored["molecules"]])
            molecule = restored["molecules"][0]
            self.assertNotIn("path", molecule)
            self.assertEqual(f"/api/files/{molecule['id']}/download", molecule["download_url"])
            downloaded = client.get(molecule["download_url"])
            self.assertEqual(200, downloaded.status_code)
            self.assertEqual(structure.read_bytes(), downloaded.data)
            self.assertIn("candidate.pdb", downloaded.headers["Content-Disposition"])
            downloaded.close()
            file_id = restored["files"][0]["id"]
            self.assertEqual(
                400,
                client.post(
                    "/api/change_chat_file",
                    json={"file_id": file_id, "is_visible": "yes"},
                ).status_code,
            )
            client.post("/api/logout")
            client.post("/api/register", json={"username": "bob", "password": "pw",
                "email": "b@example.test"})
            client.post("/api/login", json={"username": "bob", "password": "pw"})
            self.assertEqual(404, client.get(molecule["download_url"]).status_code)
            user_id, payload, history = service.calls[0]
            self.assertEqual((user_id, payload["chat_id"], payload["message"]),
                             ("user-alice", "chat-1", "Assess LRRK2"))
            self.assertEqual(payload["files"], [
                {"path": str(upload)}, {"path": str(structure)}
            ])
            self.assertEqual(history, ())
            saved = models.ChatHistory.records[0].message_data
            self.assertTrue(saved[0]["isUser"])
            self.assertEqual(saved[-1]["content"], "source-backed answer")
        self.assertEqual(_app_identity(), before)

    @unittest.skipUnless(
        importlib.util.find_spec("flask_sqlalchemy"),
        "Flask-SQLAlchemy web dependency is optional",
    )
    def test_real_models_persist_login_and_chat_to_sqlite(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            runtime = Path(directory)
            config = WebLaunchConfig(
                ROOT,
                runtime,
                "test-secret",
                "sqlite:///" + str(runtime / "app.sqlite3"),
                runtime / "memory.sqlite3",
            )
            app = create_web_app(
                config,
                service=_Service(),
                _runtime_boundary=runtime,
            )
            app.config.update(TESTING=True)
            client = app.test_client()
            self.assertTrue(
                client.post(
                    "/api/register",
                    json={
                        "username": "real-model-user",
                        "password": "pw",
                        "email": "real-model@example.test",
                    },
                ).get_json()["success"]
            )
            first_login = client.post(
                "/api/login",
                json={"username": "real-model-user", "password": "pw"},
            ).get_json()
            self.assertTrue(first_login["success"])
            response = client.post(
                "/api/chat",
                json={"chat_id": "sqlite-chat", "message": "Assess LRRK2", "files": []},
                buffered=True,
            )
            self.assertIn("source-backed answer", response.get_data(as_text=True))
            history = client.post(
                "/api/chat_history",
                json={"user_id": "not-the-session-user", "chat_id": "sqlite-chat"},
            )
            self.assertFalse(history.get_json()["success"])
            self.assertTrue(client.post("/api/logout").get_json()["success"])
            self.assertTrue(
                client.post(
                    "/api/register",
                    json={
                        "username": "second-real-user",
                        "password": "pw",
                        "email": "second-real@example.test",
                    },
                ).get_json()["success"]
            )
            second_login = client.post(
                "/api/login",
                json={"username": "second-real-user", "password": "pw"},
            ).get_json()
            self.assertTrue(second_login["success"])
            second_response = client.post(
                "/api/chat",
                json={
                    "chat_id": "sqlite-chat",
                    "message": "Assess EGFR",
                    "files": [],
                },
                buffered=True,
            )
            self.assertIn("source-backed answer", second_response.get_data(as_text=True))
            self.assertTrue((runtime / "app.sqlite3").is_file())
            from app import models as real_models

            with app.app_context():
                records = real_models.ChatHistory.query.filter_by(
                    conversation_id="sqlite-chat"
                ).all()
                self.assertEqual(2, len(records))
                self.assertEqual(
                    {first_login["user_id"], second_login["user_id"]},
                    {record.user_id for record in records},
                )
                real_models.db.session.remove()
                real_models.db.engine.dispose()

    @unittest.skipUnless(importlib.util.find_spec("flask"), "Flask web dependency is optional")
    def test_request_errors_return_json_statuses(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            runtime = Path(directory)
            config = WebLaunchConfig(
                ROOT,
                runtime,
                "test-secret",
                "sqlite:///" + str(runtime / "app.sqlite3"),
                runtime / "memory.sqlite3",
            )
            app = create_web_app(
                config,
                service=_Service(),
                models_module=_models(),
                _runtime_boundary=runtime,
            )
            app.config.update(TESTING=True)
            client = app.test_client()
            self.assertEqual(401, client.post("/api/chat", json={}).status_code)
            self.assertEqual(400, client.post("/api/register", data="invalid").status_code)

    @unittest.skipUnless(importlib.util.find_spec("flask"), "Flask web dependency is optional")
    def test_page_declares_only_available_first_party_assets(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            runtime = Path(directory)
            config = WebLaunchConfig(
                ROOT,
                runtime,
                "test-secret",
                "sqlite:///" + str(runtime / "app.sqlite3"),
                runtime / "memory.sqlite3",
            )
            app = create_web_app(
                config,
                service=_Service(),
                models_module=_models(),
                _runtime_boundary=runtime,
            )
            app.config.update(TESTING=True)
            client = app.test_client()
            page = client.get("/")
            self.assertEqual(200, page.status_code)
            markup = page.get_data(as_text=True)
            for asset in (
                "app.js",
                "logo.png",
                "styles.css",
                "user.png",
            ):
                self.assertIn(f"assets/{asset}", markup)
                response = client.get(f"/assets/{asset}")
                self.assertEqual(200, response.status_code)
                response.close()
            self.assertNotIn("app_v", markup)
            script_response = client.get("/assets/app.js")
            script = script_response.get_data(as_text=True)
            script_response.close()
            self.assertIn("Interactive 3D preview", script)
            self.assertIn("drag to rotate", script)
            self.assertNotIn("molstar", script.lower())

    def test_manager_rejects_upload_escape_and_symlinks(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            root = Path(directory) / "uploads"
            root.mkdir()
            inside = root / "inside.txt"
            outside = Path(directory) / "outside.txt"
            inside.write_text("inside", encoding="utf-8")
            outside.write_text("outside", encoding="utf-8")
            manager = WebResearchManager(_Service(), lambda user: "chat", root)
            list(manager.chat_stream("user", [{"text": "read"}, {"file": str(inside)}], []))
            with self.assertRaises(ValueError):
                manager.chat_stream("user", [{"file": str(outside)}], [])
            link = root / "link.txt"
            link.symlink_to(outside)
            with self.assertRaises(ValueError):
                manager.chat_stream("user", [{"file": str(link)}], [])

    def test_empty_secret_and_runtime_escape_fail_closed(self):
        with patch.dict("os.environ", {"SECRET_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "SECRET_KEY"):
                WebLaunchConfig.from_env(ROOT)
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            runtime = Path(directory)
            config = WebLaunchConfig(ROOT, runtime, "secret",
                "sqlite:///" + str(runtime / "app.sqlite3"), runtime / "memory.sqlite3")
            with self.assertRaises(ValueError):
                create_web_app(config, service=_Service(), models_module=_models())

    def test_environment_defaults_keep_database_and_memory_in_runtime(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            project = Path(directory)
            values = {"SECRET_KEY": "secret", "FROGENT_MEMORY_DB": "",
                      "FROGENT_DATABASE_URI": ""}
            with patch.dict(os.environ, values):
                config = WebLaunchConfig.from_env(project)
            runtime = project / "runtime" / "app"
            self.assertEqual(config.memory_path, runtime / "research-memory.sqlite3")
            self.assertEqual(config.database_uri, "sqlite:///" + str(runtime / "app.sqlite3"))


if __name__ == "__main__":
    unittest.main()
