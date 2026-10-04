"""Audit/activity log model."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class AuditLog(TimestampMixin, db.Model):
    """A record of a significant action performed by a user."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    action = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(80), index=True)
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))

    # Relationships
    user = db.relationship("User", backref="audit_logs")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AuditLog {self.id} {self.action!r}>"
