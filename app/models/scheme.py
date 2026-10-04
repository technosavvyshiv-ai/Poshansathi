"""Welfare scheme models: catalogue and beneficiary links."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin
from app.utils.constants import SchemeStatus


class WelfareScheme(TimestampMixin, db.Model):
    """A government welfare/nutrition scheme described for the demo."""

    __tablename__ = "welfare_schemes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    category = db.Column(db.String(80))
    description = db.Column(db.Text)
    target_group = db.Column(db.String(150))
    benefits = db.Column(db.Text)
    eligibility = db.Column(db.Text)
    required_documents = db.Column(db.Text)
    application_info = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Relationships
    beneficiary_links = db.relationship(
        "BeneficiaryScheme",
        back_populates="scheme",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<WelfareScheme {self.name!r}>"


class BeneficiaryScheme(TimestampMixin, db.Model):
    """Association between a beneficiary and a scheme."""

    __tablename__ = "beneficiary_schemes"

    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(
        db.Integer,
        db.ForeignKey("beneficiaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheme_id = db.Column(
        db.Integer,
        db.ForeignKey("welfare_schemes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = db.Column(
        db.Enum(SchemeStatus, name="scheme_status"),
        nullable=False,
        default=SchemeStatus.ELIGIBLE,
    )
    applied_date = db.Column(db.Date)
    notes = db.Column(db.Text)

    # Relationships
    beneficiary = db.relationship("Beneficiary", back_populates="scheme_links")
    scheme = db.relationship("WelfareScheme", back_populates="beneficiary_links")

    __table_args__ = (
        db.UniqueConstraint(
            "beneficiary_id", "scheme_id", name="uq_beneficiary_scheme"
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<BeneficiaryScheme beneficiary={self.beneficiary_id} "
            f"scheme={self.scheme_id}>"
        )
