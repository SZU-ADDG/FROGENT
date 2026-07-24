"""Persistent web accounts, conversations, and uploaded-file metadata."""

import base64
import secrets
import uuid
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    user_id = db.Column(db.String(50), unique=True, nullable=False)
    salt = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def set_salt(self, password, email):
        salt = secrets.token_bytes(16)
        self.salt = base64.b64encode(salt).decode("utf-8")
        self.user_id = str(
            uuid.uuid3(uuid.NAMESPACE_OID, (self.username + self.salt).encode("utf-8"))
        )
        self.password_hash = generate_password_hash(password + self.salt)
        self.email = email

    def check_password(self, password):
        return check_password_hash(self.password_hash, password + self.salt)

    def get_user_id(self):
        return self.user_id


class ChatFiles(db.Model):
    __tablename__ = "chat_files"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    conversation_id = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(1024), nullable=False)
    is_molecular = db.Column(db.Boolean, nullable=False)
    is_clear = db.Column(db.Boolean, nullable=False)
    is_visible = db.Column(db.Boolean, nullable=False)
    format = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "filename": self.filename,
            "path": self.path,
            "is_molecular": self.is_molecular,
            "is_clear": self.is_clear,
            "is_visible": self.is_visible,
            "format": self.format,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def get_by_conversation_id(cls, user_id, conversation_id):
        return cls.query.filter_by(
            user_id=user_id, conversation_id=conversation_id, is_clear=False
        ).all()

    @classmethod
    def get_by_id(cls, file_id):
        return cls.query.filter_by(id=file_id).first()

    @classmethod
    def create(cls, **values):
        record = cls(**values)
        db.session.add(record)
        db.session.commit()
        return record.id

    def update(self, is_clear=None, is_visible=None):
        if is_clear is not None and not isinstance(is_clear, bool):
            raise ValueError("is_clear must be boolean")
        if is_visible is not None and not isinstance(is_visible, bool):
            raise ValueError("is_visible must be boolean")
        if is_clear is not None:
            self.is_clear = is_clear
        if is_visible is not None:
            self.is_visible = is_visible
        db.session.commit()
        return True


class ChatHistory(db.Model):
    __tablename__ = "chat_history"
    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "conversation_id", name="uq_chat_history_user_conversation"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    conversation_id = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    message_data = db.Column(db.JSON, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_data": self.message_data,
        }

    @classmethod
    def create(cls, **values):
        record = cls(**values)
        db.session.add(record)
        db.session.commit()
        return record.id

    @classmethod
    def get_by_conversation_id(cls, user_id, conversation_id):
        return cls.query.filter_by(
            user_id=user_id, conversation_id=conversation_id
        ).first()

    def update(self, new_message_data=None, new_title=None):
        if new_message_data is not None:
            self.message_data = new_message_data
        if new_title is not None:
            self.title = new_title
        db.session.commit()
        return True
