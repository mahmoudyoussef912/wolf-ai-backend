from flask import Blueprint, request, jsonify
from app.models.database import db
from app.models.theme import Theme
from app.middleware.auth import require_admin

theme_bp = Blueprint("theme", __name__)


def _get_or_create_theme():
    """Ensure default theme exists."""
    theme = Theme.query.first()
    if not theme:
        theme = Theme()
        db.session.add(theme)
        db.session.commit()
    return theme


@theme_bp.route("/api/theme", methods=["GET"])
def get_theme():
    """Public endpoint: get current theme settings."""
    theme = _get_or_create_theme()
    return jsonify(theme.to_dict())


@theme_bp.route("/api/admin/theme", methods=["PUT"])
@require_admin
def admin_update_theme():
    return jsonify({"error": "Theme updates from admin are disabled"}), 403
