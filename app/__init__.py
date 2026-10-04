"""PoshanSathi Flask application factory.

``create_app`` builds and returns a configured Flask application.  Keeping
construction inside a factory makes the app easy to test and ready for the
feature modules added in later phases.
"""

from __future__ import annotations

import logging
import os

from flask import Flask, render_template

from app.extensions import db

# Imported here (not at module top) to avoid importing config twice.
from config import config as config_map


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure a Flask application instance.

    :param config_name: one of ``development`` | ``testing`` | ``production``.
        Defaults to the ``FLASK_CONFIG`` environment variable, or
        ``development`` when unset.
    """
    config_name = config_name or os.getenv("FLASK_CONFIG", "default")
    app = Flask(__name__)

    app.config.from_object(config_map.get(config_name, config_map["default"]))

    _configure_logging(app)
    _register_extensions(app)
    _register_models()
    _register_cli(app)
    _register_request_hooks(app)
    _register_context_processors(app)
    _register_blueprints(app)
    _register_error_handlers(app)

    app.logger.info("PoshanSathi application created (%s).", config_name)
    return app


def _configure_logging(app: Flask) -> None:
    """Attach a simple, consistent stream logger."""
    level = getattr(
        logging,
        str(app.config.get("LOG_LEVEL", "INFO")).upper(),
        logging.INFO,
    )
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
    )

    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(level)


def _register_extensions(app: Flask) -> None:
    """Bind extension instances to the application."""
    db.init_app(app)


def _register_models() -> None:
    """Import the model package so every table is registered on the metadata."""
    import app.models  # noqa: F401


def _register_cli(app: Flask) -> None:
    """Register the database CLI commands."""
    from app.cli import register_cli

    register_cli(app)


def _register_request_hooks(app: Flask) -> None:
    """Resolve the signed-in user once per request."""
    from app.utils.helpers import load_logged_in_user

    app.before_request(load_logged_in_user)


def _register_context_processors(app: Flask) -> None:
    """Expose auth-related globals to every template."""
    from app.utils.constants import ROLE_LABELS, UserRole
    from app.utils.helpers import age_years, current_user

    app.add_template_filter(age_years, "age_years")

    @app.context_processor
    def inject_auth_context():
        return {
            "current_user": current_user(),
            "UserRole": UserRole,
            "role_labels": ROLE_LABELS,
        }


def _register_blueprints(app: Flask) -> None:
    """Register application blueprints."""
    from app.routes.admin import bp as admin_bp
    from app.routes.attendance import bp as attendance_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.beneficiaries import bp as beneficiaries_bp
    from app.routes.centres import bp as centres_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.growth import bp as growth_bp
    from app.routes.main import bp as main_bp
    from app.routes.maternal import bp as maternal_bp
    from app.routes.nutrition import bp as nutrition_bp
    from app.routes.vaccination import bp as vaccination_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(beneficiaries_bp)
    app.register_blueprint(centres_bp)
    app.register_blueprint(growth_bp)
    app.register_blueprint(vaccination_bp)
    app.register_blueprint(maternal_bp)
    app.register_blueprint(nutrition_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)


def _register_error_handlers(app: Flask) -> None:
    """Register friendly error pages."""

    @app.errorhandler(403)
    def forbidden(error):  # pragma: no cover - trivial
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):  # pragma: no cover - trivial
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):  # pragma: no cover - trivial
        return render_template("errors/500.html"), 500
