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
    """Admin endpoint: update theme colors, branding, and content text."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    theme = _get_or_create_theme()

    # Update colors
    if "colors" in data:
        colors = data["colors"]
        for key in ("bg_primary", "bg_secondary", "bg_tertiary", "accent", "accent_hover",
                    "text_primary", "text_secondary", "border", "success", "error"):
            if key in colors and colors[key]:
                setattr(theme, key, colors[key])

    # Update branding
    if "branding" in data:
        branding = data["branding"]
        if "app_name" in branding and branding["app_name"]:
            theme.app_name = branding["app_name"]
        if "app_description" in branding and branding["app_description"]:
            theme.app_description = branding["app_description"]
        if "logo_url" in branding and branding["logo_url"]:
            theme.logo_url = branding["logo_url"]
        if "favicon_url" in branding and branding["favicon_url"]:
            theme.favicon_url = branding["favicon_url"]

    # Update content
    if "content" in data:
        content = data["content"]
        if "login_title" in content and content["login_title"]:
            theme.login_title = content["login_title"]
        if "login_subtitle" in content and content["login_subtitle"]:
            theme.login_subtitle = content["login_subtitle"]
        if "register_title" in content and content["register_title"]:
            theme.register_title = content["register_title"]
        if "register_subtitle" in content and content["register_subtitle"]:
            theme.register_subtitle = content["register_subtitle"]

    db.session.commit()
    return jsonify({"message": "Theme updated", "theme": theme.to_dict()})
