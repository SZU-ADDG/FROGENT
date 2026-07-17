import hashlib
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from frogent_plugin.app_v4_bridge import AppV4ResearchManager
from frogent_plugin.app_v4_launcher import AppV4LaunchConfig, create_app_v4_research


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
SOURCE = PROJECT / "sources" / "frogent"


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
        def get_by_conversation_id(cls, conversation_id):
            return cls.query.filter_by(conversation_id=conversation_id).first()

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
        def get_by_conversation_id(cls, conversation_id):
            return cls.query.filter_by(conversation_id=conversation_id, is_clear=False).all()

        def to_dict(self): return dict(self.__dict__)

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


def _source_identity():
    return {str(path.relative_to(SOURCE)): (path.stat().st_size, path.stat().st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest())
            for path in SOURCE.rglob("*") if path.is_file()}


class AppV4LauncherTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("flask"), "Flask web dependency is optional")
    def test_real_routes_stream_research_and_save_history_without_source_writes(self):
        before, cwd, prior_models = _source_identity(), Path.cwd(), sys.modules.get("models")
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            runtime = Path(directory)
            upload = runtime / "uploads" / "paper.txt"
            upload.parent.mkdir()
            upload.write_text("attachment", encoding="utf-8")
            config = AppV4LaunchConfig(ROOT, SOURCE, runtime, "test-secret",
                "sqlite:///" + str(runtime / "app.sqlite3"), runtime / "memory.sqlite3")
            models, service = _models(), _Service()
            app = create_app_v4_research(config, service=service, models_module=models,
                                         _runtime_boundary=runtime)
            self.assertEqual(Path.cwd(), cwd)
            self.assertIs(sys.modules.get("models"), prior_models)
            app.config.update(TESTING=True)
            client = app.test_client()
            self.assertTrue(client.post("/api/register", json={"username": "alice",
                "password": "pw", "email": "a@example.test"}).get_json()["success"])
            self.assertTrue(client.post("/api/login", json={"username": "alice",
                "password": "pw"}).get_json()["success"])
            response = client.post("/api/chat", json={"chat_id": "chat-1",
                "message": "Assess LRRK2", "files": [{"filename": "paper.txt",
                "path": str(upload), "is_molecular": False, "format": "txt"}]}, buffered=True)
            body = response.get_data(as_text=True)
            self.assertIn('"content":"source-backed answer"', body)
            self.assertIn('"stop":true', body)
            self.assertIn("data: [DONE]", body)
            user_id, payload, history = service.calls[0]
            self.assertEqual((user_id, payload["chat_id"], payload["message"]),
                             ("user-alice", "chat-1", "Assess LRRK2"))
            self.assertEqual(payload["files"], [{"path": str(upload)}])
            self.assertEqual(history, ())
            saved = models.ChatHistory.records[0].message_data
            self.assertTrue(saved[0]["isUser"])
            self.assertEqual(saved[-1]["content"], "source-backed answer")
        self.assertEqual(_source_identity(), before)

    def test_manager_rejects_upload_escape_and_symlinks(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            root = Path(directory) / "uploads"
            root.mkdir()
            inside = root / "inside.txt"
            outside = Path(directory) / "outside.txt"
            inside.write_text("inside", encoding="utf-8")
            outside.write_text("outside", encoding="utf-8")
            manager = AppV4ResearchManager(_Service(), lambda user: "chat", root)
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
                AppV4LaunchConfig.from_env(ROOT, SOURCE)
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            runtime = Path(directory)
            config = AppV4LaunchConfig(ROOT, SOURCE, runtime, "secret",
                "sqlite:///" + str(runtime / "app.sqlite3"), runtime / "memory.sqlite3")
            with self.assertRaises(ValueError):
                create_app_v4_research(config, service=_Service(), models_module=_models())

    def test_environment_defaults_keep_database_and_memory_in_runtime(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            project = Path(directory)
            plugin = project / "plugins" / "frogent-drug-design"
            source = project / "sources" / "frogent"
            plugin.mkdir(parents=True)
            source.mkdir(parents=True)
            (source / "app_v4.py").write_text("# fixture\n", encoding="utf-8")
            values = {"SECRET_KEY": "secret", "FROGENT_MEMORY_DB": "",
                      "FROGENT_DATABASE_URI": ""}
            with patch.dict(os.environ, values):
                config = AppV4LaunchConfig.from_env(plugin, source)
            runtime = plugin / ".runtime" / "app-v4"
            self.assertEqual(config.memory_path, runtime / "research-memory.sqlite3")
            self.assertEqual(config.database_uri, "sqlite:///" + str(runtime / "app-v4.sqlite3"))


if __name__ == "__main__":
    unittest.main()
