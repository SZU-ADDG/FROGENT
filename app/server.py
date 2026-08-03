"""Maintained Flask surface for the FROGENT Agent."""

import importlib
import logging
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import Flask, Response, jsonify, request, send_file, send_from_directory, session
from flask import stream_with_context
from werkzeug.utils import secure_filename

from app.chat import (
    file_path,
    load_chat_sessions,
    new_chat,
    require_text,
    split_files,
    stream_chat,
    user_content,
)

ALLOWED_EXTENSIONS = {
    "csv", "docx", "fa", "fasta", "html", "pdf", "pptx", "tsv", "txt",
    "xls", "xlsx",
}
MOLECULAR_EXTENSIONS = {"cif", "mol", "mol2", "pdb", "sdf"}
LOGGER = logging.getLogger(__name__)


def build_app(*, secret_key, database_uri, upload_root, manager, models_module=None):
    models = models_module or importlib.import_module("app.models")
    uploads = Path(upload_root).resolve()
    app_root = Path(__file__).resolve().parent
    web = Flask(__name__, static_folder=str(uploads), static_url_path="/uploads")
    web.config.update(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=database_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=str(uploads),
    )
    models.db.init_app(web)
    state = {"sessions": {}, "manager": manager, "models": models, "uploads": uploads}
    _register_errors(web)
    _register_routes(web, state, app_root)
    with web.app_context():
        models.db.create_all()
    return web


def _register_routes(web, state, app_root):
    models, sessions = state["models"], state["sessions"]

    @web.get("/")
    def index():
        return (app_root / "templates" / "index.html").read_text(encoding="utf-8")

    @web.get("/assets/<path:filename>")
    def assets(filename):
        return send_from_directory(app_root / "assets", filename)

    @web.post("/api/register")
    def register():
        payload = _payload()
        username, password, email = _credentials(payload)
        if models.User.query.filter_by(username=username).first():
            return jsonify(success=False, message="用户名已存在")
        try:
            user = models.User(username=username)
            user.set_salt(password, email)
            models.db.session.add(user)
            models.db.session.commit()
        except Exception:
            models.db.session.rollback()
            LOGGER.exception("user registration failed")
            return jsonify(success=False, message="注册失败")
        return jsonify(success=True, message="注册成功")

    @web.post("/api/login")
    def login():
        payload = _payload()
        username = require_text(payload.get("username"), "username")
        password = require_text(payload.get("password"), "password")
        user = models.User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            return jsonify(success=False, message="Incorrect username or password")
        user_id = user.get_user_id()
        session.update(user_id=user_id, username=username)
        chats = load_chat_sessions(models, user_id, state["uploads"])
        sessions[user_id] = {
            "username": username,
            "login_time": datetime.now(),
            "chat_sessions": chats,
        }
        return jsonify(
            success=True,
            message=f"欢迎回来，{username}!",
            user_id=user_id,
            chat_sessions=chats,
        )

    @web.post("/api/logout")
    def logout():
        user_id = session.get("user_id")
        if isinstance(user_id, str):
            sessions.pop(user_id, None)
        session.clear()
        return jsonify(success=True, message="已成功注销")

    @web.post("/api/chat_history")
    def chat_history():
        payload, user_id = _payload(), _session_user(sessions)
        if payload.get("user_id") != user_id:
            return jsonify(success=False, message="用户身份不匹配")
        chat_id = require_text(payload.get("chat_id"), "chat_id")
        chat = sessions[user_id]["chat_sessions"].get(chat_id)
        if chat is None:
            return jsonify(success=False, message="聊天不存在")
        result = dict(chat)
        result.update(split_files(models, user_id, chat_id, state["uploads"]))
        return jsonify(success=True, messages="获取消息成功", chat_session=result)

    @web.post("/api/chat")
    def chat():
        user_id = _session_user(sessions)
        payload = _payload()
        message = payload.get("message", "")
        if not isinstance(message, str):
            raise ValueError("message must be text")
        message = message.strip()
        chat_id = require_text(payload.get("chat_id"), "chat_id")
        files = payload.get("files", [])
        if not isinstance(files, list) or (not message and not files):
            return jsonify(success=False, message="消息和文件均不能为空")
        chat_session = sessions[user_id]["chat_sessions"].setdefault(
            chat_id, new_chat(chat_id, message)
        )
        content, names = user_content(message, files)
        history = tuple(chat_session["messages"])
        chat_session["messages"].append(
            {"content": content, "isUser": True, "fileNames": names}
        )
        stream = stream_chat(
            state, user_id, chat_id, chat_session, message, files, history
        )
        return Response(
            stream_with_context(stream),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @web.post("/api/upload")
    def upload():
        user_id = _session_user(sessions)
        incoming = request.files.getlist("file")
        if not incoming:
            return jsonify(success=False, message="没有文件")
        destination = state["uploads"] / user_id
        destination.mkdir(parents=True, exist_ok=True)
        uploaded = []
        for item in incoming:
            filename = secure_filename(item.filename or "")
            if not _allowed(filename):
                return jsonify(success=False, message=f"文件类型不允许或文件名为空：{filename}")
            extension = filename.rsplit(".", 1)[1].lower()
            path = destination / f"{uuid4().hex}-{filename}"
            path.resolve(strict=False).relative_to(state["uploads"])
            item.save(path)
            uploaded.append(
                {
                    "filename": filename,
                    "path": str(path),
                    "is_molecular": extension in MOLECULAR_EXTENSIONS,
                    "format": extension if extension in MOLECULAR_EXTENSIONS else None,
                }
            )
        return jsonify(success=True, message="文件上传成功", files=uploaded)

    @web.post("/api/change_chat_file")
    def change_chat_file():
        payload, user_id = _payload(), _session_user(sessions)
        record = models.ChatFiles.get_by_id(payload.get("file_id"))
        if record is None or record.user_id != user_id:
            return jsonify(success=False, message="文件不存在")
        changed = record.update(
            is_clear=payload.get("is_clear"), is_visible=payload.get("is_visible")
        )
        return jsonify(success=bool(changed), message="更新成功" if changed else "更新失败")

    @web.get("/api/files/<int:file_id>/download")
    def download_chat_file(file_id):
        user_id = _session_user(sessions)
        record = models.ChatFiles.get_by_id(file_id)
        if (
            record is None
            or record.user_id != user_id
            or bool(getattr(record, "is_clear", False))
        ):
            return jsonify(success=False, message="文件不存在"), 404
        path = Path(file_path(record.to_dict(), state["uploads"]))
        download_name = secure_filename(record.filename) or path.name
        return send_file(
            path,
            as_attachment=True,
            download_name=download_name,
            max_age=0,
        )


def _payload():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValueError("request JSON must be an object")
    return value


def _credentials(payload):
    return (
        require_text(payload.get("username"), "username"),
        require_text(payload.get("password"), "password"),
        require_text(payload.get("email"), "email"),
    )


def _session_user(sessions):
    user_id = session.get("user_id")
    if not isinstance(user_id, str) or user_id not in sessions:
        raise PermissionError("请先登录")
    return user_id


def _allowed(filename):
    return (
        bool(filename)
        and "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in (ALLOWED_EXTENSIONS | MOLECULAR_EXTENSIONS)
    )


def _register_errors(web):
    @web.errorhandler(ValueError)
    def bad_request(error):
        return jsonify(success=False, message=str(error)), 400

    @web.errorhandler(PermissionError)
    def unauthorized(error):
        return jsonify(success=False, message=str(error)), 401
