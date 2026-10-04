"""Attendance model."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.constants import AttendanceStatus


class Attendance(TimestampMixin, db.Model):
    """Daily present/absent record for a child."""

    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(
        db.Integer,
        db.ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    centre_id = db.Column(
        db.Integer,
        db.ForeignKey("anganwadi_centres.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(
        db.Enum(AttendanceStatus, name="attendance_status"),
        nullable=False,
        default=AttendanceStatus.PRESENT,
    )
    note = db.Column(db.String(255))
    recorded_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
    )

    # Relationships
    child = db.relationship("Child", back_populates="attendance_records")
    centre = db.relationship("AnganwadiCentre")
    recorded_by = db.relationship("User", foreign_keys=[recorded_by_id])

    __table_args__ = (
        db.UniqueConstraint(
            "child_id", "attendance_date", name="uq_attendance_child_date"
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Attendance child={self.child_id} {self.attendance_date}>"
