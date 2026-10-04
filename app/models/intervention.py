"""Intervention / follow-up model."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class Intervention(TimestampMixin, db.Model):
    """An action taken after a home visit, optionally linked to a visit."""

    __tablename__ = "interventions"

    id = db.Column(db.Integer, primary_key=True)
    home_visit_id = db.Column(
        db.Integer,
        db.ForeignKey("home_visits.id", ondelete="CASCADE"),
        index=True,
    )
    beneficiary_id = db.Column(
        db.Integer,
        db.ForeignKey("beneficiaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recorded_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
    )
    intervention_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    outcome = db.Column(db.Text)
    intervention_date = db.Column(db.Date, nullable=False, index=True)
    follow_up_date = db.Column(db.Date)

    # Relationships
    home_visit = db.relationship("HomeVisit", back_populates="interventions")
    beneficiary = db.relationship("Beneficiary", back_populates="interventions")
    recorded_by = db.relationship("User", foreign_keys=[recorded_by_id])

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Intervention {self.id} {self.intervention_type!r}>"
