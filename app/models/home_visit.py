"""Home visit model."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.constants import VisitStatus, VisitType


class HomeVisit(TimestampMixin, db.Model):
    """A scheduled/completed home visit for a beneficiary."""

    __tablename__ = "home_visits"

    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(
        db.Integer,
        db.ForeignKey("beneficiaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    centre_id = db.Column(
        db.Integer,
        db.ForeignKey("anganwadi_centres.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    visit_type = db.Column(
        db.Enum(VisitType, name="visit_type"),
        nullable=False,
        default=VisitType.ROUTINE,
    )
    assigned_worker_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
    )
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    completed_date = db.Column(db.Date)
    status = db.Column(
        db.Enum(VisitStatus, name="visit_status"),
        nullable=False,
        default=VisitStatus.SCHEDULED,
        index=True,
    )
    visit_notes = db.Column(db.Text)
    follow_up_required = db.Column(db.Boolean, nullable=False, default=False)
    follow_up_date = db.Column(db.Date)

    # Relationships
    beneficiary = db.relationship("Beneficiary", back_populates="home_visits")
    centre = db.relationship("AnganwadiCentre")
    assigned_worker = db.relationship("User", foreign_keys=[assigned_worker_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    interventions = db.relationship(
        "Intervention", back_populates="home_visit", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<HomeVisit {self.id} beneficiary={self.beneficiary_id}>"
