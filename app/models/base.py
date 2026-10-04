"""Shared model helpers.

``TimestampMixin`` adds the ``created_at`` / ``updated_at`` columns used by
almost every PoshanSathi table.  Keeping them in one place avoids repeating the
same two columns across the schema.
"""

from __future__ import annotations

from datetime import datetime

from app.extensions import db


class TimestampMixin:
    """Adds creation and last-update timestamps to a model."""

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=db.func.now(),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=db.func.now(),
    )
