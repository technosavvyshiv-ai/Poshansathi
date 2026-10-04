"""User model (authentication identifiers + role + centre link).

Authentication *routes* are implemented in Phase 2.  Phase 1 defines the table
and password helpers so the schema and seed data are complete.
"""

from __future__ import annotations

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.constants import UserRole


class User(TimestampMixin, db.Model):
    """An application user: ADMIN, AWW, SUPERVISOR or OFFICER."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    centre_id = db.Column(
        db.Integer,
        db.ForeignKey("anganwadi_centres.id", ondelete="SET NULL"),
        index=True,
    )
    full_name = db.Column(db.String(150), nullable=False)
    username = db.Column(db.String(80), nullable=False, unique=True)
    email = db.Column(db.String(150), unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole, name="user_role"), nullable=False)
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime)

    # Relationships
    centre = db.relationship("AnganwadiCentre", back_populates="users")

    __table_args__ = (
        db.Index("ix_users_role", "role"),
    )

    # --- Password helpers -------------------------------------------------
    def set_password(self, password: str) -> None:
        """Hash and store ``password``."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Return True when ``password`` matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.username!r} ({self.role})>"
