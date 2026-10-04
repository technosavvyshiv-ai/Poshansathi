"""Maternal health (ANC) record model."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.constants import RiskLevel


class MaternalHealthRecord(TimestampMixin, db.Model):
    """A single antenatal-care measurement for a mother."""

    __tablename__ = "maternal_health_records"

    id = db.Column(db.Integer, primary_key=True)
    mother_id = db.Column(
        db.Integer,
        db.ForeignKey("mothers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recorded_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
    )
    visit_date = db.Column(db.Date, nullable=False, index=True)
    pregnancy_month = db.Column(db.Integer)
    weight_kg = db.Column(db.Numeric(5, 2))
    haemoglobin = db.Column(db.Numeric(4, 1))
    systolic_bp = db.Column(db.Integer)
    diastolic_bp = db.Column(db.Integer)
    risk_category = db.Column(
        db.Enum(RiskLevel, name="risk_level"),
        nullable=False,
        default=RiskLevel.LOW,
    )
    next_follow_up_date = db.Column(db.Date)
    notes = db.Column(db.Text)

    # Relationships
    mother = db.relationship("Mother", back_populates="health_records")
    recorded_by = db.relationship("User", foreign_keys=[recorded_by_id])

    __table_args__ = (
        db.UniqueConstraint(
            "mother_id", "visit_date", name="uq_maternal_mother_visit"
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<MaternalHealthRecord mother={self.mother_id} {self.visit_date}>"
