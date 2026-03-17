from app.models.database import db
from datetime import datetime, timezone

_utcnow = lambda: datetime.now(timezone.utc)


class Theme(db.Model):
    __tablename__ = "themes"
    id = db.Column(db.Integer, primary_key=True)
    
    # Colors
    bg_primary = db.Column(db.String(7), default="#070e17")
    bg_secondary = db.Column(db.String(7), default="#0f1724")
    bg_tertiary = db.Column(db.String(7), default="#162233")
    accent = db.Column(db.String(7), default="#14b8a6")
    accent_hover = db.Column(db.String(7), default="#0d9488")
    text_primary = db.Column(db.String(7), default="#e6edf5")
    text_secondary = db.Column(db.String(7), default="#9fb1c7")
    border = db.Column(db.String(7), default="#233347")
    success = db.Column(db.String(7), default="#22c55e")
    error = db.Column(db.String(7), default="#ef4444")
    
    # Branding
    app_name = db.Column(db.String(100), default="WOLF AI")
    app_description = db.Column(db.Text, default="Advanced AI Assistant")
    logo_url = db.Column(db.String(500), nullable=True)
    favicon_url = db.Column(db.String(500), nullable=True)
    
    # Content
    login_title = db.Column(db.String(200), default="Welcome Back")
    login_subtitle = db.Column(db.String(200), default="Sign in to WOLF AI")
    register_title = db.Column(db.String(200), default="Create Account")
    register_subtitle = db.Column(db.String(200), default="Join WOLF AI for free")
    
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "colors": {
                "bg_primary": self.bg_primary,
                "bg_secondary": self.bg_secondary,
                "bg_tertiary": self.bg_tertiary,
                "accent": self.accent,
                "accent_hover": self.accent_hover,
                "text_primary": self.text_primary,
                "text_secondary": self.text_secondary,
                "border": self.border,
                "success": self.success,
                "error": self.error,
            },
            "branding": {
                "app_name": self.app_name,
                "app_description": self.app_description,
                "logo_url": self.logo_url,
                "favicon_url": self.favicon_url,
            },
            "content": {
                "login_title": self.login_title,
                "login_subtitle": self.login_subtitle,
                "register_title": self.register_title,
                "register_subtitle": self.register_subtitle,
            },
            "updated_at": self.updated_at.isoformat(),
        }
