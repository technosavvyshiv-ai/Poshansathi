"""Pytest fixtures for PoshanSathi tests."""

from __future__ import annotations

import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture()
def app():
    """A Flask app configured for testing (in-memory SQLite) with tables."""
    application = create_app("testing")
    with application.app_context():
        import app.models  # noqa: F401  (register all tables)

        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    """A Flask test client."""
    return app.test_client()


@pytest.fixture()
def db(app):
    """The SQLAlchemy extension bound to the testing app."""
    return _db
