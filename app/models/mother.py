"""Mother model: pregnant and lactating women.

Type-specific details for a beneficiary whose ``beneficiary_type`` is
``PREGNANT_WOMAN`` or ``LACTATING_MOTHER``.
"""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.constants import RiskLevel


class Mother(TimestampMixin, db.Model):
    """Pregnancy / lactation profile linked one-to-one to a beneficiary."""

    __tablename__ = "mothers"

    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(
        db.Integer,
        db.ForeignKey("beneficiaries.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    age = db.Column(db.Integer)
    husband_name = db.Column(db.String(150))
    pregnancy_number = db.Column(db.Integer)
    last_menstrual_period = db.Column(db.Date)
    expected_delivery_date = db.Column(db.Date)
    delivery_date = db.Column(db.Date)
    blood_group = db.Column(db.String(5))
    height_cm = db.Column(db.Numeric(5, 2))
    current_risk_level = db.Column(
        db.Enum(RiskLevel, name="risk_level"),
        nullable=False,
        default=RiskLevel.LOW,
    )

    # Relationships
    beneficiary = db.relationship("Beneficiary", back_populates="mother")
    children = db.relationship("Child", back_populates="mother")
    health_records = db.relationship(
        "MaternalHealthRecord",
        back_populates="mother",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Mother beneficiary={self.beneficiary_id}>"
