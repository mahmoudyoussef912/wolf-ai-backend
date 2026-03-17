import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import create_engine, text
from app.config import Config
from app.models.database import db
from app.models.store import seed_database

limiter = Limiter(key_func=get_remote_address, default_limits=["300 per hour"])


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    # Fail open to local sqlite when managed postgres is temporarily unavailable.
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if db_uri.startswith("postgresql://"):
        try:
            probe_engine = create_engine(db_uri, pool_pre_ping=True)
            with probe_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            app.logger.exception("PostgreSQL probe failed, falling back to sqlite: %s", e)
            app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/wolf.db"

    # Wide CORS policy for hosted frontend domains (including dynamic Vercel URLs).
    CORS(
        app,
        resources={r"/api/*": {"origins": "*"}},
        supports_credentials=False,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    limiter.init_app(app)

    os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)

    db.init_app(app)
    from app.models.theme import Theme  # noqa: F401

    with app.app_context():
        try:
            db.create_all()
            seed_database()
        except Exception as e:
            app.logger.exception("Database initialization failed: %s", e)

    # Register blueprints for different parts of the application
    from app.routes.chat import chat_bp
    from app.routes.image import image_bp
    from app.routes.upload import upload_bp
    from app.routes.admin import admin_bp
    from app.routes.auth import auth_bp
    from app.routes.conversations import conversations_bp
    from app.routes.theme import theme_bp

    app.register_blueprint(chat_bp)
    app.register_blueprint(image_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(conversations_bp)
    app.register_blueprint(theme_bp)

    @app.route("/api/health")
    def health():
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        db_backend = "postgresql" if db_uri.startswith("postgresql://") else "sqlite"
        return {"status": "ok", "app": "WOLF AI", "database": db_backend}

    # Error Handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Endpoint not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(429)
    def ratelimit_handler(e):
        # The default Flask-Limiter response is not JSON
        return jsonify({"error": "Too many requests. Please slow down."}), 429

    @app.errorhandler(500)
    def internal_server_error(e):
        app.logger.exception("Unhandled server error: %s", e)
        return jsonify({"error": "An internal server error occurred"}), 500

    return app
