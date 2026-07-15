"""
============================================================
 Genesis AI — Application Factory (app.py)
 Entry point for the Flask application.
 Uses the Application Factory pattern so that the app
 instance can be created with different configurations
 (testing, development, production) without code changes.
============================================================
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load environment variables from .env file BEFORE anything else.
# This ensures all configuration values are available at import time.
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Shared SQLAlchemy instance — created here, bound to the app in create_app().
# This pattern avoids circular imports across blueprints/agents.
# ---------------------------------------------------------------------------
db = SQLAlchemy()


def create_app() -> Flask:
    """
    Application factory function.

    Returns a fully configured Flask application with:
      - SQLAlchemy ORM (Project Memory)
      - CORS headers for the React-style frontend
      - All API blueprints registered under /api
      - Upload and ChromaDB storage directories created on first run

    Usage:
        from app import create_app
        app = create_app()
        app.run()
    """
    app = Flask(
        __name__,
        template_folder="templates",   # Jinja2 templates live here
        static_folder="static",        # CSS / JS / assets live here
    )

    # ------------------------------------------------------------------
    # Configuration — pulled securely from environment variables.
    # All sensitive values (API keys, DB URIs) stay out of source code.
    # ------------------------------------------------------------------
    app.config["SECRET_KEY"] = os.environ.get(
        "FLASK_SECRET_KEY", "fallback-dev-secret-do-not-use-in-prod"
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///genesis_projects.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Suppresses deprecation warning

    # Maximum file upload size (default 16 MB — override via .env)
    max_mb = int(os.environ.get("MAX_CONTENT_LENGTH_MB", 16))
    app.config["MAX_CONTENT_LENGTH"] = max_mb * 1024 * 1024

    # Path where user-uploaded PDFs are stored before RAG processing
    upload_folder = os.environ.get("UPLOAD_FOLDER", "./uploads")
    app.config["UPLOAD_FOLDER"] = upload_folder

    # ------------------------------------------------------------------
    # Ensure required local directories exist at startup.
    # ------------------------------------------------------------------
    os.makedirs(upload_folder, exist_ok=True)
    chroma_path = os.environ.get("CHROMA_DB_PATH", "./chroma_store")
    os.makedirs(chroma_path, exist_ok=True)

    # ------------------------------------------------------------------
    # Initialise extensions — bind to this specific app instance.
    # ------------------------------------------------------------------
    db.init_app(app)

    # CORS: allow requests from any origin during development.
    # In production, restrict origins= to your actual frontend domain.
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ------------------------------------------------------------------
    # Register blueprints — each blueprint owns its own URL namespace.
    # ------------------------------------------------------------------
    from routes.project_api import project_bp
    from routes.export_api import export_bp

    app.register_blueprint(project_bp, url_prefix="/api")
    app.register_blueprint(export_bp, url_prefix="/api")

    # ------------------------------------------------------------------
    # Create database tables if they don't already exist.
    # In production, use Flask-Migrate for schema migrations instead.
    # ------------------------------------------------------------------
    with app.app_context():
        from models import Project, DebateLog  # noqa: F401 — registers models with SQLAlchemy
        db.create_all()

    # ------------------------------------------------------------------
    # Root route — serves the single-page application shell.
    # ------------------------------------------------------------------
    from flask import render_template

    @app.route("/")
    def index():
        """Serve the main SPA shell (templates/index.html)."""
        return render_template("index.html")

    return app


# ---------------------------------------------------------------------------
# Entrypoint for direct execution: `python app.py`
# Production deployments should use gunicorn instead:
#   gunicorn "app:create_app()" --bind 0.0.0.0:5000 --workers 4
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    flask_app = create_app()
    debug_mode = os.environ.get("FLASK_ENV", "production") == "development"
    flask_app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=debug_mode,
    )
