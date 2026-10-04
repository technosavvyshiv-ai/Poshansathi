"""Application configuration.

Configuration is selected through the ``FLASK_CONFIG`` environment variable
(``development`` | ``testing`` | ``production``).  Secrets and the database
URL come from the environment (loaded from ``.env``), never hard-coded.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Project root (folder containing this file).
BASE_DIR = Path(__file__).resolve().parent

# Load variables from ".env" if present.  Real .env is git-ignored.
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration shared by all environments."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-key")

    # SQLAlchemy / MySQL.  Format: mysql+pymysql://user:pass@host:port/db
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://poshansathi:poshansathi@localhost:3306/poshansathi",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # --- Session / cookie security (Phase 2 authentication) ----------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv(
        "SESSION_COOKIE_SECURE", "false"
    ).lower() in ("1", "true", "yes")
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(os.getenv("SESSION_LIFETIME_HOURS", "8"))
    )


class DevelopmentConfig(Config):
    """Local development."""

    DEBUG = True


class TestingConfig(Config):
    """Automated tests — uses in-memory SQLite, no MySQL required."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    SQLALCHEMY_ENGINE_OPTIONS = {}


class ProductionConfig(Config):
    """Production."""

    DEBUG = False
    SESSION_COOKIE_SECURE = True


# Map config names -> classes; "default" is used when nothing is specified.
config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
