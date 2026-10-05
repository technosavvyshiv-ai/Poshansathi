"""Beneficiary model.

A beneficiary is the common record for every person served by a centre.  The
type-specific details live in the ``children`` and ``mothers`` tables, linked
one-to-one through ``beneficiary_id``.
"""

from __future__ import annotations

from datetime import date

from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.constants import BeneficiaryType, Gender, RecordStatus


class Beneficiary(TimestampMixin, db.Model):
    """Common demographic record shared by children and mothers."""

    __tablename__ = "beneficiaries"

    id = db.Column(db.Integer, primary_key=True)
    centre_id = db.Column(
        db.Integer,
        db.ForeignKey("anganwadi_centres.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    beneficiary_type = db.Column(
        db.Enum(BeneficiaryType, name="beneficiary_type"), nullable=False, index=True
    )
    full_name = db.Column(db.String(150), nullable=False, index=True)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.Enum(Gender, name="gender"))
    guardian_name = db.Column(db.String(150))
    contact = db.Column(db.String(20))
    address = db.Column(db.String(255))
    status = db.Column(
        db.Enum(RecordStatus, name="record_status"),
        nullable=False,
        default=RecordStatus.ACTIVE,
        index=True,
    )
    registration_date = db.Column(db.Date, nullable=False, default=date.today)

    # Relationships
    centre = db.relationship("AnganwadiCentre", back_populates="beneficiaries")
    child = db.relationship(
        "Child",
        back_populates="beneficiary",
        uselist=False,
        cascade="all, delete-orphan",
    )
    mother = db.relationship(
        "Mother",
        back_populates="beneficiary",
        uselist=False,
        cascade="all, delete-orphan",
    )
    scheme_links = db.relationship(
        "BeneficiaryScheme",
        back_populates="beneficiary",
        cascade="all, delete-orphan",
    )
    nutrition_distributions = db.relationship(
        "NutritionDistribution",
        back_populates="beneficiary",
        cascade="all, delete-orphan",
    )
    home_visits = db.relationship(
        "HomeVisit", back_populates="beneficiary", cascade="all, delete-orphan"
    )
    interventions = db.relationship(
        "Intervention", back_populates="beneficiary", cascade="all, delete-orphan"
    )
    alerts = db.relationship(
        "Alert",
        back_populates="beneficiary",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Beneficiary {self.id} {self.full_name!r} ({self.beneficiary_type})>"
