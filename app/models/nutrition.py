"""Nutrition models: item catalogue, per-centre inventory and distributions."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class NutritionItem(TimestampMixin, db.Model):
    """Catalogue of nutrition/ration items (e.g. Take-Home Ration)."""

    __tablename__ = "nutrition_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    category = db.Column(db.String(80))
    unit = db.Column(db.String(30), nullable=False, default="kg")
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Relationships
    inventory_items = db.relationship("Inventory", back_populates="item")
    distributions = db.relationship("NutritionDistribution", back_populates="item")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<NutritionItem {self.name!r}>"


class Inventory(TimestampMixin, db.Model):
    """Stock position for one item at one centre.

    ``available_quantity`` is a convenience property implementing the plan's
    ``Opening + Received - Distributed`` calculation.  Actual stock movements
    are recorded by the services added in later phases.
    """

    __tablename__ = "inventory"

    id = db.Column(db.Integer, primary_key=True)
    centre_id = db.Column(
        db.Integer,
        db.ForeignKey("anganwadi_centres.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id = db.Column(
        db.Integer,
        db.ForeignKey("nutrition_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    opening_stock = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    received_quantity = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    distributed_quantity = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    minimum_stock = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    unit = db.Column(db.String(30), nullable=False, default="kg")
    expiry_date = db.Column(db.Date)
    received_date = db.Column(db.Date)

    # Relationships
    centre = db.relationship("AnganwadiCentre", back_populates="inventory_items")
    item = db.relationship("NutritionItem", back_populates="inventory_items")

    __table_args__ = (
        db.UniqueConstraint("centre_id", "item_id", name="uq_inventory_centre_item"),
    )

    @property
    def available_quantity(self):
        """Current stock = opening + received - distributed."""
        return (
            (self.opening_stock or 0)
            + (self.received_quantity or 0)
            - (self.distributed_quantity or 0)
        )

    @property
    def is_low_stock(self) -> bool:
        """True when the current stock has reached the configured minimum."""
        return self.available_quantity <= (self.minimum_stock or 0)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Inventory centre={self.centre_id} item={self.item_id}>"


class NutritionDistribution(TimestampMixin, db.Model):
    """A quantity of an item distributed to a beneficiary by a worker."""

    __tablename__ = "nutrition_distributions"

    id = db.Column(db.Integer, primary_key=True)
    beneficiary_id = db.Column(
        db.Integer,
        db.ForeignKey("beneficiaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id = db.Column(
        db.Integer,
        db.ForeignKey("nutrition_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    centre_id = db.Column(
        db.Integer,
        db.ForeignKey("anganwadi_centres.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    worker_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    distribution_date = db.Column(db.Date, nullable=False, index=True)
    notes = db.Column(db.Text)

    # Relationships
    beneficiary = db.relationship(
        "Beneficiary", back_populates="nutrition_distributions"
    )
    item = db.relationship("NutritionItem", back_populates="distributions")
    centre = db.relationship("AnganwadiCentre")
    worker = db.relationship("User", foreign_keys=[worker_id])

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<NutritionDistribution beneficiary={self.beneficiary_id} "
            f"item={self.item_id}>"
        )
