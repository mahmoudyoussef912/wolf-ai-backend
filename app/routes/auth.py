import jwt
import requests as http_requests
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, current_app, g
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.database import db, User
from app.middleware.auth import require_auth

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/google-config", methods=["GET"])
def google_config():
    client_id = current_app.config.get("GOOGLE_CLIENT_ID", "")
    return jsonify({"enabled": bool(client_id), "client_id": client_id})


def _create_token(user):
    payload = {
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=current_app.config.get("JWT_EXPIRY_HOURS", 72)),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    email = data.get("email", "").strip().lower()
    name = data.get("name", "").strip()
    password = data.get("password", "")

    if not email or not name or not password:
        return jsonify({"error": "Email, name, and password are required"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if "@" not in email or "." not in email:
        return jsonify({"error": "Invalid email format"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(
        email=email,
        name=name,
        password_hash=generate_password_hash(password),
        provider="local",
        role="user",
    )
    db.session.add(user)
    db.session.commit()

    token = _create_token(user)
    return jsonify({"token": token, "user": user.to_dict()}), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.password_hash:
        return jsonify({"error": "Invalid email or password"}), 401

    if not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = _create_token(user)
    return jsonify({"token": token, "user": user.to_dict()})


@auth_bp.route("/api/auth/google", methods=["POST"])
def google_auth():
    data = request.get_json()
    if not data or not data.get("credential"):
        return jsonify({"error": "Google credential required"}), 400

    credential = data["credential"]

    # Verify Google ID token
    try:
        google_resp = http_requests.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}",
            timeout=10,
        )
        if google_resp.status_code != 200:
            return jsonify({"error": "Invalid Google token"}), 401

        google_data = google_resp.json()

        # Verify the token was issued for this app
        expected_client_id = current_app.config.get("GOOGLE_CLIENT_ID", "")
        if expected_client_id and google_data.get("aud") != expected_client_id:
            return jsonify({"error": "Invalid Google token"}), 401

        email = google_data.get("email", "").lower()
        name = google_data.get("name", email.split("@")[0])
        picture = google_data.get("picture", "")
        sub = google_data.get("sub", "")

        if not email:
            return jsonify({"error": "Could not get email from Google"}), 400

    except Exception:
        return jsonify({"error": "Failed to verify Google token"}), 400

    # Find or create user with deterministic linking behavior:
    # 1) Prefer existing local/email account (merge into same account)
    # 2) Fallback to existing google-sub account
    # 3) Create fresh account
    user_by_email = User.query.filter_by(email=email).first()
    user_by_sub = User.query.filter_by(provider_id=sub).first() if sub else None

    if user_by_email:
        user = user_by_email
        if picture and not user.avatar_url:
            user.avatar_url = picture
        if sub and not user.provider_id:
            user.provider_id = sub
        if user.provider not in ("local", "google"):
            user.provider = "google"
    elif user_by_sub:
        user = user_by_sub
        if email and not user.email:
            user.email = email
        if name and user.name != name:
            user.name = name
        if picture and not user.avatar_url:
            user.avatar_url = picture
        user.provider = "google"
    else:
        user = User(
            email=email,
            name=name,
            avatar_url=picture,
            provider="google",
            provider_id=sub,
            role="user",
        )
        db.session.add(user)

    db.session.commit()

    token = _create_token(user)
    return jsonify({"token": token, "user": user.to_dict()})


@auth_bp.route("/api/auth/me", methods=["GET"])
@require_auth
def get_me():
    return jsonify(g.current_user.to_dict())
