"""In-app notification model."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class Notification(TimestampMixin, db.Model):
    """An in-app notification addressed to a user."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    category = db.Column(db.String(80), index=True)
    related_type = db.Column(db.String(50))
    related_id = db.Column(db.Integer)
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    read_at = db.Column(db.DateTime)

    # Relationships
    user = db.relationship("User", backref="notifications")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Notification {self.id} user={self.user_id}>"
