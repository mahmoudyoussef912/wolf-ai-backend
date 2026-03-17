from functools import wraps
from flask import request, jsonify, g, current_app
import jwt
from app.models.database import User, db


def _verify_token():
    """Helper to verify JWT token and load user into g."""
    token = _extract_token()
    if not token:
        return jsonify({"error": "Authentication required"}), 401
    try:
        payload = jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])
        user = db.session.get(User, payload["user_id"])
        if not user:
            return jsonify({"error": "User not found"}), 401
        g.current_user = user
        return None  # No error
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired. Please login again."}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401


def _extract_token():
    """Extracts the token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split("Bearer ", 1)[1]
    return None


def require_auth(f):
    """Decorator to ensure a user is authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        error_response = _verify_token()
        if error_response:
            return error_response
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Decorator to ensure a user is an admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        error_response = _verify_token()
        if error_response:
            return error_response
        if g.current_user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated
