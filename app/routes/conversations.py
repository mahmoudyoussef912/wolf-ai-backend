from flask import Blueprint, request, jsonify, g
from app.models.database import db, Conversation, ChatMessage
from app.middleware.auth import require_auth

conversations_bp = Blueprint("conversations", __name__)


@conversations_bp.route("/api/conversations", methods=["GET"])
@require_auth
def list_conversations():
    convs = (Conversation.query
             .filter_by(user_id=g.current_user.id)
             .order_by(Conversation.updated_at.desc())
             .all())
    return jsonify([c.to_dict() for c in convs])


@conversations_bp.route("/api/conversations", methods=["POST"])
@require_auth
def create_conversation():
    data = request.get_json() or {}
    title = data.get("title", "New Chat")

    conv = Conversation(
        user_id=g.current_user.id,
        title=title,
    )
    db.session.add(conv)
    db.session.commit()
    return jsonify(conv.to_dict()), 201


@conversations_bp.route("/api/conversations/<int:conv_id>/messages", methods=["GET"])
@require_auth
def get_messages(conv_id):
    conv = db.get_or_404(Conversation, conv_id)
    if conv.user_id != g.current_user.id:
        return jsonify({"error": "Access denied"}), 403

    messages = (ChatMessage.query
                .filter_by(conversation_id=conv_id)
                .order_by(ChatMessage.created_at.asc())
                .all())
    return jsonify([m.to_dict() for m in messages])


@conversations_bp.route("/api/conversations/<int:conv_id>", methods=["DELETE"])
@require_auth
def delete_conversation(conv_id):
    conv = db.get_or_404(Conversation, conv_id)
    if conv.user_id != g.current_user.id:
        return jsonify({"error": "Access denied"}), 403

    db.session.delete(conv)
    db.session.commit()
    return jsonify({"message": "Conversation deleted"})


@conversations_bp.route("/api/conversations/<int:conv_id>/title", methods=["PUT"])
@require_auth
def update_title(conv_id):
    conv = db.get_or_404(Conversation, conv_id)
    if conv.user_id != g.current_user.id:
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json() or {}
    new_title = data.get("title")
    if new_title is not None:
        conv.title = str(new_title)[:200]
    db.session.commit()
    return jsonify(conv.to_dict())
