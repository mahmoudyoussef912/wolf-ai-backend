import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # General
    # In production, this should be a complex, random, securely stored string
    SECRET_KEY = os.getenv("SECRET_KEY")
    # In production, set FLASK_DEBUG to "false" or don't set it
    IS_DEV = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # API Keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    
    # Admin
    ADMIN_USER = os.getenv("ADMIN_USER", "admin")
    ADMIN_PASS = os.getenv("ADMIN_PASS", "") # No default password
    
    # File Uploads
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # Database
    _database_url = os.getenv("DATABASE_URL", "").strip()
    if _database_url:
        # Render may provide postgres://; SQLAlchemy expects postgresql://
        if _database_url.startswith("postgres://"):
            _database_url = _database_url.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = _database_url
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "wolf.db"
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_SECRET = os.getenv("JWT_SECRET")
    JWT_EXPIRY_HOURS = 72

    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    
    def __init__(self):
        """
        In a non-debug environment, enforce presence of critical secrets.
        """
        if not self.IS_DEV:
            if not self.SECRET_KEY:
                raise ValueError("SECRET_KEY must be set in production environment.")
            if not self.JWT_SECRET:
                raise ValueError("JWT_SECRET must be set in production environment.")
