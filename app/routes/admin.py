from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from app.models.store import get_stats, get_chat_logs, get_settings, update_settings
from app.models.database import db, User, Conversation, ChatMessage, UploadedFile, ArchivedConversation, ArchivedMessage
from app.middleware.auth import require_admin
from app.models.store import archive_and_delete_conversation

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/api/admin/stats", methods=["GET"])
@require_admin
def admin_stats():
    return jsonify(get_stats())


@admin_bp.route("/api/admin/logs", methods=["GET"])
@require_admin
def admin_logs():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    return jsonify(get_chat_logs(page, per_page))


@admin_bp.route("/api/admin/settings", methods=["GET"])
@require_admin
def admin_get_settings():
    settings = get_settings()
    for key_name in ("groq_api_key", "hf_api_token", "openrouter_api_key"):
        if settings.get(key_name):
            key = settings[key_name]
            settings[key_name] = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
    return jsonify(settings)


@admin_bp.route("/api/admin/settings", methods=["PUT"])
@require_admin
def admin_update_settings():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    updated = update_settings(data)
    return jsonify({"message": "Settings updated", "settings": updated})


@admin_bp.route("/api/admin/users", methods=["GET"])
@require_admin
def admin_users():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    query = User.query.order_by(User.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "users": [u.to_dict() for u in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
    })


@admin_bp.route("/api/admin/users", methods=["POST"])
@require_admin
def admin_create_user():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    email = str(data.get("email", "")).strip().lower()
    name = str(data.get("name", "")).strip()
    password = str(data.get("password", ""))
    role = str(data.get("role", "user")).strip().lower()

    if not email or not name or not password:
        return jsonify({"error": "Email, name, and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if role not in ("user", "admin"):
        return jsonify({"error": "Role must be 'user' or 'admin'"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 409

    user = User(
        email=email,
        name=name,
        password_hash=generate_password_hash(password),
        provider="local",
        role=role,
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User created", "user": user.to_dict()}), 201


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@require_admin
def admin_delete_user(user_id):
    user = db.get_or_404(User, user_id)

    # Archive all user conversations/messages before deleting the account.
    conversations = Conversation.query.filter_by(user_id=user.id).all()
    for conv in conversations:
        archive_and_delete_conversation(
            conv,
            deleted_by_user_id=user_id,
            reason="user_account_delete",
        )

    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted"})


@admin_bp.route("/api/admin/users/<int:user_id>/role", methods=["PUT"])
@require_admin
def admin_update_role(user_id):
    user = db.get_or_404(User, user_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    role = data.get("role")
    if role not in ("user", "admin"):
        return jsonify({"error": "Role must be 'user' or 'admin'"}), 400
    user.role = role
    db.session.commit()
    return jsonify({"message": "Role updated", "user": user.to_dict()})


@admin_bp.route("/api/admin/users/<int:user_id>/messages", methods=["GET"])
@require_admin
def admin_user_messages(user_id):
    user = db.get_or_404(User, user_id)
    include_deleted = str(request.args.get("include_deleted", "true")).lower() == "true"

    active_messages = (
        ChatMessage.query
        .filter_by(user_id=user.id)
        .order_by(ChatMessage.created_at.desc())
        .all()
    )
    active_rows = [{**m.to_dict(), "source": "active"} for m in active_messages]

    archived_rows = []
    if include_deleted:
        archived_messages = (
            ArchivedMessage.query
            .filter_by(user_id=user.id)
            .order_by(ArchivedMessage.deleted_at.desc())
            .all()
        )
        archived_rows = [{**m.to_dict(), "source": "archived"} for m in archived_messages]

    return jsonify({
        "user": user.to_dict(),
        "active_count": len(active_rows),
        "archived_count": len(archived_rows),
        "messages": active_rows + archived_rows,
    })


@admin_bp.route("/api/admin/conversations", methods=["GET"])
@require_admin
def admin_conversations():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    query = Conversation.query.order_by(Conversation.updated_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    rows = []
    for conv in pagination.items:
        msg_count = ChatMessage.query.filter_by(conversation_id=conv.id).count()
        rows.append({
            "id": conv.id,
            "title": conv.title,
            "user_id": conv.user_id,
            "user_email": conv.user.email if conv.user else "",
            "message_count": msg_count,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else conv.created_at.isoformat(),
        })

    return jsonify({
        "conversations": rows,
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
    })


@admin_bp.route("/api/admin/conversations/<int:conv_id>/messages", methods=["GET"])
@require_admin
def admin_conversation_messages(conv_id):
    conv = db.get_or_404(Conversation, conv_id)
    messages = (
        ChatMessage.query
        .filter_by(conversation_id=conv.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return jsonify({
        "conversation": {
            "id": conv.id,
            "title": conv.title,
            "user_id": conv.user_id,
            "user_email": conv.user.email if conv.user else "",
        },
        "messages": [m.to_dict() for m in messages],
    })


@admin_bp.route("/api/admin/conversations/<int:conv_id>", methods=["DELETE"])
@require_admin
def admin_delete_conversation(conv_id):
    conv = db.get_or_404(Conversation, conv_id)
    archived = archive_and_delete_conversation(conv, deleted_by_user_id=None, reason="admin_delete")
    return jsonify({"message": "Conversation deleted", "archived_id": archived.id})


@admin_bp.route("/api/admin/files", methods=["GET"])
@require_admin
def admin_files():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    query = UploadedFile.query.order_by(UploadedFile.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "files": [
            {
                "id": f.id,
                "user_id": f.user_id,
                "filename": f.filename,
                "file_type": f.file_type,
                "mime_type": f.mime_type,
                "created_at": f.created_at.isoformat(),
            }
            for f in pagination.items
        ],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
    })


@admin_bp.route("/api/admin/files/<string:file_id>", methods=["DELETE"])
@require_admin
def admin_delete_file(file_id):
    item = db.get_or_404(UploadedFile, file_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "File deleted"})


@admin_bp.route("/api/admin/archived-conversations", methods=["GET"])
@require_admin
def admin_archived_conversations():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    user_id = request.args.get("user_id", type=int)

    query = ArchivedConversation.query
    if user_id:
        query = query.filter_by(original_user_id=user_id)

    pagination = query.order_by(ArchivedConversation.deleted_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    rows = []
    for conv in pagination.items:
        msg_count = ArchivedMessage.query.filter_by(archived_conversation_id=conv.id).count()
        row = conv.to_dict()
        row["message_count"] = msg_count
        rows.append(row)

    return jsonify({
        "conversations": rows,
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
    })


@admin_bp.route("/api/admin/archived-conversations/<int:archived_id>/messages", methods=["GET"])
@require_admin
def admin_archived_messages(archived_id):
    conv = db.get_or_404(ArchivedConversation, archived_id)
    messages = (
        ArchivedMessage.query
        .filter_by(archived_conversation_id=archived_id)
        .order_by(ArchivedMessage.created_at.asc())
        .all()
    )
    return jsonify({
        "conversation": conv.to_dict(),
        "messages": [m.to_dict() for m in messages],
    })


@admin_bp.route("/api/admin/analytics", methods=["GET"])
@require_admin
def admin_analytics():
    users = User.query.count()
    active_conversations = Conversation.query.count()
    active_messages = ChatMessage.query.count()
    archived_conversations = ArchivedConversation.query.count()
    archived_messages = ArchivedMessage.query.count()
    uploads = UploadedFile.query.count()

    top_users = (
        db.session.query(User.id, User.email, db.func.count(ChatMessage.id).label("messages"))
        .join(ChatMessage, ChatMessage.user_id == User.id)
        .group_by(User.id, User.email)
        .order_by(db.desc("messages"))
        .limit(10)
        .all()
    )

    return jsonify({
        "overview": {
            "users": users,
            "active_conversations": active_conversations,
            "active_messages": active_messages,
            "archived_conversations": archived_conversations,
            "archived_messages": archived_messages,
            "uploads": uploads,
        },
        "top_users": [
            {"user_id": u.id, "email": u.email, "messages": int(u.messages)}
            for u in top_users
        ],
    })
