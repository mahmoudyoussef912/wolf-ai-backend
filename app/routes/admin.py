from flask import Blueprint, request, jsonify
from app.models.store import get_stats, get_chat_logs, get_settings, update_settings
from app.models.database import db, User, Conversation, ChatMessage, UploadedFile
from app.middleware.auth import require_admin

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


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@require_admin
def admin_delete_user(user_id):
    user = db.get_or_404(User, user_id)
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
    db.session.delete(conv)
    db.session.commit()
    return jsonify({"message": "Conversation deleted"})


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
