import uuid
from flask import Blueprint, request, jsonify, g
from app.services.file_service import process_file, allowed_file
from app.models.store import store_file
from app.middleware.auth import require_auth

upload_bp = Blueprint("upload", __name__)


@upload_bp.route("/api/upload", methods=["POST"])
@require_auth
def handle_upload():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if not file.filename:
            return jsonify({"error": "No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "File type not allowed. Supported: pdf, txt, png, jpg, jpeg, webp"}), 400

        file_data = process_file(file)
        file_id = str(uuid.uuid4())
        store_file(file_id, file_data, user_id=g.current_user.id)

        return jsonify({
            "file_id": file_id,
            "filename": file_data["filename"],
            "type": file_data["type"],
        })

    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500
