import re
from flask import Blueprint, request, jsonify, g
from app.services.llm_service import chat
from app.models.store import add_chat_log, get_file
from app.models.database import db, Conversation, ChatMessage
from app.middleware.auth import require_auth

chat_bp = Blueprint("chat", __name__)

MAX_MESSAGE_LENGTH = 8000

DEVELOPER_NAME = "Mahmoud Youssef Elshoraky"
DEVELOPER_INFO_EN = "Founder and lead developer of WOLF AI."
DEVELOPER_INFO_AR = "مؤسس ومطور WOLF AI الرئيسي."


def _looks_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text or ""))


def _is_developer_question(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False

    arabic_hits = ["مين المطور", "من المطور", "مين طور", "مين عملك", "مطورك", "صاحبك", "صاحب البرنامج"]
    english_hits = [
        "who is your developer",
        "who developed you",
        "who made you",
        "developer name",
        "who is the developer",
        "your developer",
        "about developer",
    ]
    return any(k in t for k in arabic_hits) or any(k in t for k in english_hits)


def _developer_reply(user_text: str) -> str:
    if _looks_arabic(user_text):
        return (
            f"المطور هو {DEVELOPER_NAME}. "
            f"{DEVELOPER_INFO_AR}"
        )
    return (
        f"The developer is {DEVELOPER_NAME}. "
        f"{DEVELOPER_INFO_EN}"
    )


@chat_bp.route("/api/chat", methods=["POST"])
@require_auth
def handle_chat():
    try:
        data = request.get_json()
        if not data or not data.get("message"):
            return jsonify({"error": "Message is required"}), 400

        message = data["message"]
        if len(message) > MAX_MESSAGE_LENGTH:
            return jsonify({"error": f"Message too long (max {MAX_MESSAGE_LENGTH} chars)"}), 400

        file_ids = data.get("file_ids", [])
        conversation_id = data.get("conversation_id")

        # Auto-create conversation if none provided
        if not conversation_id:
            title = message[:60] + ("…" if len(message) > 60 else "")
            conv = Conversation(user_id=g.current_user.id, title=title)
            db.session.add(conv)
            db.session.flush()
            conversation_id = conv.id

        files = [f for fid in file_ids if (f := get_file(fid))]

        # Deterministic response for developer identity questions.
        if _is_developer_question(message):
            response_text = _developer_reply(message)
            add_chat_log(
                message, response_text,
                msg_type="text",
                conversation_id=conversation_id,
                user_id=g.current_user.id,
                provider_used="system",
            )
            return jsonify({
                "response": response_text,
                "type": "text",
                "provider": "system",
                "conversation_id": conversation_id,
            })

        # Build conversation history for multi-turn context
        history = []
        if conversation_id:
            past = (
                ChatMessage.query
                .filter_by(conversation_id=conversation_id)
                .filter(ChatMessage.msg_type == "text")
                .order_by(ChatMessage.created_at.asc())
                .limit(40)
                .all()
            )
            history = [
                {"role": m.role, "content": m.content}
                for m in past
                if m.role in ("user", "assistant")
            ]

        result = chat(message, files=files or None, history=history or None)

        response_text = result["text"] if isinstance(result, dict) else result
        provider = result.get("provider", "") if isinstance(result, dict) else ""

        add_chat_log(
            message, response_text,
            msg_type="text",
            conversation_id=conversation_id,
            user_id=g.current_user.id,
            provider_used=provider,
        )

        return jsonify({
            "response": response_text,
            "type": "text",
            "provider": provider,
            "conversation_id": conversation_id,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Chat failed: {str(e)}"}), 500
