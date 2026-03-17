from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

_utcnow = lambda: datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)  # null for OAuth users
    avatar_url = db.Column(db.String(500), nullable=True)
    provider = db.Column(db.String(20), default="local")  # 'local' or 'google'
    provider_id = db.Column(db.String(255), nullable=True)  # Google sub ID
    role = db.Column(db.String(20), default="user")  # 'user' or 'admin'
    created_at = db.Column(db.DateTime, default=_utcnow)

    conversations = db.relationship("Conversation", backref="user", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "provider": self.provider,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }


class Conversation(db.Model):
    __tablename__ = "conversations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), default="New Chat")
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    messages = db.relationship("ChatMessage", backref="conversation", lazy=True,
                               order_by="ChatMessage.created_at", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else self.created_at.isoformat(),
        }


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    msg_type = db.Column(db.String(20), default="text")  # 'text', 'image', 'error'
    image_url = db.Column(db.Text, nullable=True)
    provider_used = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self):
        d = {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "type": self.msg_type,
            "timestamp": self.created_at.isoformat(),
        }
        if self.image_url:
            d["image"] = self.image_url
        if self.provider_used:
            d["provider"] = self.provider_used
        return d


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=True)


class UploadedFile(db.Model):
    __tablename__ = "uploaded_files"
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=True)
    mime_type = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)


class ArchivedConversation(db.Model):
    __tablename__ = "archived_conversations"
    id = db.Column(db.Integer, primary_key=True)
    original_conversation_id = db.Column(db.Integer, nullable=False, index=True)
    original_user_id = db.Column(db.Integer, nullable=False, index=True)
    user_email = db.Column(db.String(255), nullable=True)
    user_name = db.Column(db.String(100), nullable=True)
    title = db.Column(db.String(200), default="Archived Chat")
    deleted_by_user_id = db.Column(db.Integer, nullable=True)
    deleted_reason = db.Column(db.String(50), default="user_delete")
    created_at = db.Column(db.DateTime, default=_utcnow)
    deleted_at = db.Column(db.DateTime, default=_utcnow, index=True)

    messages = db.relationship(
        "ArchivedMessage",
        backref="archived_conversation",
        lazy=True,
        order_by="ArchivedMessage.created_at",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "original_conversation_id": self.original_conversation_id,
            "original_user_id": self.original_user_id,
            "user_email": self.user_email,
            "user_name": self.user_name,
            "title": self.title,
            "deleted_by_user_id": self.deleted_by_user_id,
            "deleted_reason": self.deleted_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }


class ArchivedMessage(db.Model):
    __tablename__ = "archived_messages"
    id = db.Column(db.Integer, primary_key=True)
    archived_conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("archived_conversations.id"),
        nullable=False,
        index=True,
    )
    original_message_id = db.Column(db.Integer, nullable=True)
    original_conversation_id = db.Column(db.Integer, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    msg_type = db.Column(db.String(20), default="text")
    image_url = db.Column(db.Text, nullable=True)
    provider_used = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)
    deleted_at = db.Column(db.DateTime, default=_utcnow, index=True)

    def to_dict(self):
        d = {
            "id": self.id,
            "archived_conversation_id": self.archived_conversation_id,
            "original_message_id": self.original_message_id,
            "original_conversation_id": self.original_conversation_id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "type": self.msg_type,
            "timestamp": self.created_at.isoformat() if self.created_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }
        if self.image_url:
            d["image"] = self.image_url
        if self.provider_used:
            d["provider"] = self.provider_used
        return d
