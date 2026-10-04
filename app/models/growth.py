"""Growth record model (weight / height / MUAC measurements)."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.constants import NutritionalStatus


class GrowthRecord(TimestampMixin, db.Model):
    """A single growth measurement for a child on a given date."""

    __tablename__ = "growth_records"

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(
        db.Integer,
        db.ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recorded_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
    )
    measurement_date = db.Column(db.Date, nullable=False, index=True)
    weight_kg = db.Column(db.Numeric(5, 2), nullable=False)
    height_cm = db.Column(db.Numeric(5, 2))
    muac_cm = db.Column(db.Numeric(5, 2))
    nutritional_status = db.Column(
        db.Enum(NutritionalStatus, name="nutritional_status")
    )
    notes = db.Column(db.Text)

    # Relationships
    child = db.relationship("Child", back_populates="growth_records")
    recorded_by = db.relationship("User", foreign_keys=[recorded_by_id])

    __table_args__ = (
        db.UniqueConstraint(
            "child_id", "measurement_date", name="uq_growth_child_date"
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<GrowthRecord child={self.child_id} {self.measurement_date}>"
