from flask import Blueprint, request, jsonify, g
from app.services.image_service import generate_image
from app.models.store import add_chat_log
from app.models.database import db, Conversation
from app.middleware.auth import require_auth

image_bp = Blueprint("image", __name__)


@image_bp.route("/api/generate-image", methods=["POST"])
@require_auth
def handle_generate_image():
    try:
        data = request.get_json()
        if not data or not data.get("prompt"):
            return jsonify({"error": "Prompt is required"}), 400

        prompt = data["prompt"]
        conversation_id = data.get("conversation_id")

        # Auto-create conversation if none provided
        if not conversation_id:
            conv = Conversation(user_id=g.current_user.id, title=f"Image: {prompt[:50]}")
            db.session.add(conv)
            db.session.flush()
            conversation_id = conv.id

        image_data_uri = generate_image(prompt)

        add_chat_log(
            f"/image {prompt}", "[Generated Image]",
            msg_type="image",
            conversation_id=conversation_id,
            user_id=g.current_user.id,
            image_url=image_data_uri,
        )

        return jsonify({
            "image": image_data_uri,
            "prompt": prompt,
            "conversation_id": conversation_id,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Image generation failed: {str(e)}"}), 500
