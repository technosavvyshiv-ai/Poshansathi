"""Vaccination record model."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.constants import VaccinationStatus


class Vaccination(TimestampMixin, db.Model):
    """A scheduled/due/administered vaccine for a child."""

    __tablename__ = "vaccinations"

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(
        db.Integer,
        db.ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vaccine_name = db.Column(db.String(120), nullable=False)
    dose_number = db.Column(db.Integer, nullable=False, default=1)
    scheduled_date = db.Column(db.Date, index=True)
    administered_date = db.Column(db.Date)
    status = db.Column(
        db.Enum(VaccinationStatus, name="vaccination_status"),
        nullable=False,
        default=VaccinationStatus.UPCOMING,
        index=True,
    )
    administered_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
    )
    notes = db.Column(db.Text)

    # Relationships
    child = db.relationship("Child", back_populates="vaccinations")
    administered_by = db.relationship("User", foreign_keys=[administered_by_id])

    __table_args__ = (
        db.UniqueConstraint(
            "child_id",
            "vaccine_name",
            "dose_number",
            name="uq_vaccination_child_vaccine_dose",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Vaccination child={self.child_id} {self.vaccine_name!r}>"
