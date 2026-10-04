"""Anganwadi centre model."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class AnganwadiCentre(TimestampMixin, db.Model):
    """An Anganwadi centre to which users and beneficiaries belong."""

    __tablename__ = "anganwadi_centres"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    code = db.Column(db.String(50), nullable=False, unique=True)
    address = db.Column(db.String(255))
    village = db.Column(db.String(120))
    district = db.Column(db.String(120))
    state = db.Column(db.String(120))
    pincode = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Relationships
    users = db.relationship(
        "User", back_populates="centre", cascade="save-update, merge"
    )
    beneficiaries = db.relationship(
        "Beneficiary", back_populates="centre", cascade="save-update, merge"
    )
    inventory_items = db.relationship(
        "Inventory", back_populates="centre", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.Index("ix_centres_district", "district"),
        db.Index("ix_centres_state", "state"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AnganwadiCentre {self.code} {self.name!r}>"
