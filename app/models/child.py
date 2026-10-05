"""Child model.

Type-specific details for a beneficiary whose ``beneficiary_type`` is
``CHILD``.  Links to health/attendance records and optionally to a mother.
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class Child(TimestampMixin, db.Model):
    """Child profile linked one-to-one to a beneficiary."""

    __tablename__ = "children"

    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(
        db.Integer,
        db.ForeignKey("beneficiaries.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    mother_id = db.Column(
        db.Integer,
        db.ForeignKey("mothers.id", ondelete="SET NULL"),
        index=True,
    )
    birth_weight_kg = db.Column(db.Numeric(5, 2))
    birth_height_cm = db.Column(db.Numeric(5, 2))
    blood_group = db.Column(db.String(5))

    # Relationships
    beneficiary = db.relationship("Beneficiary", back_populates="child")
    mother = db.relationship("Mother", back_populates="children")
    growth_records = db.relationship(
        "GrowthRecord", back_populates="child", cascade="all, delete-orphan"
    )
    vaccinations = db.relationship(
        "Vaccination", back_populates="child", cascade="all, delete-orphan"
    )
    attendance_records = db.relationship(
        "Attendance", back_populates="child", cascade="all, delete-orphan"
    )
    # ``passive_deletes`` defers to the database's ``ON DELETE CASCADE`` so a
    # deleted child/beneficiary removes its alerts instead of orphaning them.
    alerts = db.relationship(
        "Alert", back_populates="child", passive_deletes=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Child beneficiary={self.beneficiary_id}>"
