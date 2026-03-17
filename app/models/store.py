from datetime import datetime, timezone
from app.models.database import (
    db,
    ChatMessage,
    Setting,
    UploadedFile,
    User,
    Conversation,
    ArchivedConversation,
    ArchivedMessage,
)

_API_KEY_FIELDS = {"groq_api_key", "hf_api_token", "openrouter_api_key"}


def _utcnow():
    return datetime.now(timezone.utc)


def add_chat_log(user_msg, ai_msg, msg_type="text", conversation_id=None, user_id=None,
                 image_url=None, provider_used=None):
    """Add user + assistant messages to a conversation."""
    if conversation_id and user_id:
        user_message = ChatMessage(
            conversation_id=conversation_id,
            user_id=user_id,
            role="user",
            content=user_msg,
            msg_type=msg_type,
        )
        db.session.add(user_message)

        ai_message = ChatMessage(
            conversation_id=conversation_id,
            user_id=user_id,
            role="assistant",
            content=ai_msg,
            msg_type=msg_type,
            image_url=image_url,
            provider_used=provider_used,
        )
        db.session.add(ai_message)

        # Update conversation timestamp and title if first message
        conv = db.session.get(Conversation, conversation_id)
        if conv:
            conv.updated_at = _utcnow()
            if conv.title == "New Chat":
                conv.title = user_msg[:50] + ("..." if len(user_msg) > 50 else "")

        db.session.commit()
        return ai_message.to_dict()
    return None


def get_chat_logs(page=1, per_page=20):
    """Get paginated chat logs for admin. Returns individual messages."""
    query = ChatMessage.query.order_by(ChatMessage.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    logs = []
    for msg in pagination.items:
        logs.append({
            "id": str(msg.id),
            "role": msg.role,
            "content": msg.content[:200],
            "user_message": msg.content[:200] if msg.role == "user" else "",
            "ai_response": msg.content[:200] if msg.role == "assistant" else "",
            "type": msg.msg_type,
            "timestamp": msg.created_at.isoformat(),
        })

    return {
        "logs": logs,
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
    }


def get_stats():
    """Get dashboard statistics."""
    return {
        "total_users": User.query.count(),
        "messages_sent": ChatMessage.query.filter_by(role="user").count(),
        "images_generated": ChatMessage.query.filter_by(msg_type="image").count(),
        "total_conversations": Conversation.query.count(),
        "archived_conversations": ArchivedConversation.query.count(),
        "archived_messages": ArchivedMessage.query.count(),
    }


def archive_and_delete_conversation(conversation, deleted_by_user_id=None, reason="user_delete"):
    """Archive conversation and all messages, then hard-delete original records."""
    user = conversation.user
    archived_conv = ArchivedConversation(
        original_conversation_id=conversation.id,
        original_user_id=conversation.user_id,
        user_email=user.email if user else None,
        user_name=user.name if user else None,
        title=conversation.title,
        deleted_by_user_id=deleted_by_user_id,
        deleted_reason=reason,
        created_at=conversation.created_at,
    )
    db.session.add(archived_conv)
    db.session.flush()

    messages = (
        ChatMessage.query
        .filter_by(conversation_id=conversation.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    for m in messages:
        db.session.add(ArchivedMessage(
            archived_conversation_id=archived_conv.id,
            original_message_id=m.id,
            original_conversation_id=m.conversation_id,
            user_id=m.user_id,
            role=m.role,
            content=m.content,
            msg_type=m.msg_type,
            image_url=m.image_url,
            provider_used=m.provider_used,
            created_at=m.created_at,
        ))

    db.session.delete(conversation)
    db.session.commit()
    return archived_conv


def get_settings():
    """Get all settings as a dict."""
    settings = {s.key: s.value for s in Setting.query.all()}
    defaults = {
        "groq_api_key": "",
        "hf_api_token": "",
        "openrouter_api_key": "",
        "system_prompt": "You are WOLF AI, a highly capable and helpful AI assistant.",
    }
    for key, default_value in defaults.items():
        if key not in settings:
            settings[key] = default_value
    return settings


def update_settings(data):
    """Update settings. API key fields only update when a non-empty, non-masked value is provided."""
    allowed_keys = ("groq_api_key", "hf_api_token", "openrouter_api_key", "system_prompt")
    for key in allowed_keys:
        if key not in data:
            continue
        value = data[key]
        if value is None:
            continue
        # For API key fields: skip empty values and masked values (contain "...")
        if key in _API_KEY_FIELDS and (not value or "..." in value or value == "***"):
            continue
        setting = db.session.get(Setting, key)
        if setting:
            setting.value = value
        else:
            db.session.add(Setting(key=key, value=value))
    db.session.commit()
    return get_settings()


def store_file(file_id, data, user_id=None):
    """Store an uploaded file record."""
    uploaded = UploadedFile(
        id=file_id,
        user_id=user_id,
        filename=data.get("filename", "unknown"),
        file_type=data.get("type", "text"),
        content=data.get("content", ""),
        mime_type=data.get("mime_type", ""),
    )
    db.session.add(uploaded)
    db.session.commit()
    return uploaded


def get_file(file_id):
    """Get a stored file by ID."""
    f = db.session.get(UploadedFile, file_id)
    if f:
        return {
            "type": f.file_type,
            "filename": f.filename,
            "content": f.content,
            "mime_type": f.mime_type,
        }
    return None


def seed_database():
    """Seed database with admin user and default settings on first run."""
    from flask import current_app
    from werkzeug.security import generate_password_hash

    # Create admin user if not exists, requires ADMIN_PASS env var
    if not User.query.filter_by(role="admin").first():
        admin_pass = current_app.config.get("ADMIN_PASS")
        if admin_pass:
            admin = User(
                email="admin@wolf.ai",
                name="Admin",
                password_hash=generate_password_hash(admin_pass),
                role="admin",
                provider="local",
            )
            db.session.add(admin)

    # Promote configured owner/admin emails if accounts already exist.
    admin_emails = current_app.config.get("ADMIN_EMAILS", [])
    if admin_emails:
        for u in User.query.filter(User.email.in_(admin_emails)).all():
            if u.role != "admin":
                u.role = "admin"

    # Seed API keys from environment variables
    key_map = {
        "groq_api_key": "GROQ_API_KEY",
        "hf_api_token": "HF_API_TOKEN",
        "openrouter_api_key": "OPENROUTER_API_KEY",
    }
    PLACEHOLDER = "your_groq_api_key_here"

    for setting_key, config_key in key_map.items():
        val = current_app.config.get(config_key, "")
        if not val:
            continue
        existing = db.session.get(Setting, setting_key)
        if not existing:
            db.session.add(Setting(key=setting_key, value=val))
        elif existing.value in ("", PLACEHOLDER, "your_api_key_here") or not existing.value:
            existing.value = val

    # Seed default system prompt if not exists
    if not db.session.get(Setting, "system_prompt"):
        db.session.add(Setting(
            key="system_prompt",
            value="You are WOLF AI, a highly capable and helpful AI assistant. You can help with coding, analysis, creative writing, and general questions. Always provide clear, well-structured responses. Use markdown formatting when appropriate.",
        ))

    db.session.commit()
