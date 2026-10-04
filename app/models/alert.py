"""Alert model."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.constants import AlertSeverity, AlertStatus, AlertType


class Alert(TimestampMixin, db.Model):
    """A rule-based follow-up alert for a beneficiary/child."""

    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(
        db.Integer,
        db.ForeignKey("beneficiaries.id", ondelete="CASCADE"),
        index=True,
    )
    child_id = db.Column(
        db.Integer,
        db.ForeignKey("children.id", ondelete="CASCADE"),
        index=True,
    )
    alert_type = db.Column(
        db.Enum(AlertType, name="alert_type"), nullable=False, index=True
    )
    severity = db.Column(
        db.Enum(AlertSeverity, name="alert_severity"),
        nullable=False,
        default=AlertSeverity.MEDIUM,
        index=True,
    )
    message = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.Enum(AlertStatus, name="alert_status"),
        nullable=False,
        default=AlertStatus.OPEN,
        index=True,
    )
    assigned_to_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
    )
    resolved_at = db.Column(db.DateTime)
    resolution_notes = db.Column(db.Text)

    # Relationships
    beneficiary = db.relationship("Beneficiary", back_populates="alerts")
    child = db.relationship("Child", back_populates="alerts")
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Alert {self.id} {self.alert_type} ({self.status})>"
