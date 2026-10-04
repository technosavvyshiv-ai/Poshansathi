"""Nutrition and inventory business logic (Phase 7).

Responsibilities:

* nutrition item catalogue (list / create / update);
* per-centre inventory stock entries (goods received);
* beneficiary nutrition distributions (stock usage), which decrement the
  stored ``distributed_quantity``;
* the plan's stock calculation, ``Current = Opening + Received - Distributed``
  (implemented by :attr:`app.models.nutrition.Inventory.available_quantity`);
* a scoped low-stock alert that is created when the configured minimum stock is
  reached and resolved when stock is replenished.

The centralized alert lifecycle (assignment, manual status changes, home
visits) is built in Phase 9; this module only performs the scoped low-stock
integration.  Because the shared ``alerts`` table has no centre/item column, the
low-stock alert is tagged with a deterministic message marker
``[inventory:<centre_id>:<item_id>]`` so the same alert can be found and
resolved.  This is a documented, temporary integration point for Phase 9.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.extensions import db
from app.models import (
    Alert,
    AnganwadiCentre,
    Inventory,
    NutritionDistribution,
    NutritionItem,
)
from app.utils.constants import (
    AlertSeverity,
    AlertStatus,
    AlertType,
)
from app.utils.validators import (
    ValidationError,
    validate_nutrition_distribution_fields,
    validate_nutrition_item_fields,
    validate_stock_received_fields,
)


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------
def active_items():
    """Return active nutrition items ordered by name."""
    return (
        NutritionItem.query.filter_by(is_active=True)
        .order_by(NutritionItem.name.asc())
        .all()
    )


def all_items():
    """Return every nutrition item ordered by name."""
    return NutritionItem.query.order_by(NutritionItem.name.asc()).all()


def get_item(item_id: int) -> NutritionItem:
    """Return a nutrition item or raise 404."""
    return db.get_or_404(NutritionItem, item_id)


def _item_name_exists(name: str, *, exclude_id=None) -> bool:
    query = NutritionItem.query.filter(
        db.func.lower(NutritionItem.name) == name.lower()
    )
    if exclude_id is not None:
        query = query.filter(NutritionItem.id != exclude_id)
    return query.first() is not None


def create_item(form) -> NutritionItem:
    """Validate and create a nutrition catalogue item."""
    cleaned, errors = validate_nutrition_item_fields(form)
    if cleaned.get("name") and _item_name_exists(cleaned["name"]):
        errors["name"] = "A nutrition item with this name already exists."
    if errors:
        raise ValidationError(errors)

    item = NutritionItem(**cleaned)
    db.session.add(item)
    db.session.commit()
    return item


def update_item(item: NutritionItem, form) -> NutritionItem:
    """Validate and update a nutrition catalogue item."""
    cleaned, errors = validate_nutrition_item_fields(form)
    if cleaned.get("name") and _item_name_exists(
        cleaned["name"], exclude_id=item.id
    ):
        errors["name"] = "Another nutrition item with this name already exists."
    if errors:
        raise ValidationError(errors)

    for key, value in cleaned.items():
        setattr(item, key, value)
    db.session.commit()
    return item


# ---------------------------------------------------------------------------
# Inventory queries / calculations
# ---------------------------------------------------------------------------
def active_centres():
    """Return active centres ordered by name (for form dropdowns)."""
    return (
        AnganwadiCentre.query.filter_by(is_active=True)
        .order_by(AnganwadiCentre.name.asc())
        .all()
    )


def inventory_row(centre_id: int, item_id: int) -> Inventory | None:
    """Return the inventory row for ``centre`` + ``item`` or ``None``."""
    return Inventory.query.filter_by(centre_id=centre_id, item_id=item_id).first()


def inventory_list(*, scope_centre_id=None, centre_id=None) -> list[Inventory]:
    """Return inventory rows ordered by centre then item name."""
    query = Inventory.query.join(NutritionItem)
    if scope_centre_id is not None:
        query = query.filter(Inventory.centre_id == scope_centre_id)
    elif centre_id is not None:
        query = query.filter(Inventory.centre_id == centre_id)
    return query.order_by(Inventory.centre_id.asc(), NutritionItem.name.asc()).all()


def is_low_stock(inventory: Inventory) -> bool:
    """True when a *configured* minimum has been reached.

    A zero/blank minimum means "not configured" and is never flagged.
    """
    minimum = inventory.minimum_stock or 0
    return minimum > 0 and inventory.is_low_stock


def low_stock_list(*, scope_centre_id=None, centre_id=None) -> list[Inventory]:
    """Return the configured low-stock inventory rows."""
    return [
        row
        for row in inventory_list(
            scope_centre_id=scope_centre_id, centre_id=centre_id
        )
        if is_low_stock(row)
    ]


def summary(*, scope_centre_id=None) -> dict:
    """Return deterministic nutrition counts for a scope."""
    inventory = inventory_list(scope_centre_id=scope_centre_id)
    distributions = distributions_query(scope_centre_id=scope_centre_id)
    return {
        "item_count": len(active_items()),
        "inventory_rows": len(inventory),
        "low_stock_count": len([row for row in inventory if is_low_stock(row)]),
        "distribution_count": len(distributions),
    }


# ---------------------------------------------------------------------------
# Stock received
# ---------------------------------------------------------------------------
def _get_or_create_inventory(centre, item: NutritionItem) -> Inventory:
    inventory = inventory_row(centre.id, item.id)
    if inventory is None:
        inventory = Inventory(
            centre=centre,
            item=item,
            unit=item.unit,
            opening_stock=Decimal("0"),
            received_quantity=Decimal("0"),
            distributed_quantity=Decimal("0"),
            minimum_stock=Decimal("0"),
        )
        db.session.add(inventory)
        # Populate the FK columns so the low-stock alert marker is correct.
        db.session.flush()
    return inventory


def record_stock_received(centre, item: NutritionItem, form, *, actor=None) -> Inventory:
    """Validate and record goods received for ``centre`` + ``item``."""
    cleaned, errors = validate_stock_received_fields(form)
    if errors:
        raise ValidationError(errors)

    inventory = _get_or_create_inventory(centre, item)
    inventory.received_quantity = (
        (inventory.received_quantity or 0) + cleaned["quantity"]
    )
    inventory.received_date = cleaned.get("received_date") or date.today()
    if cleaned.get("expiry_date") is not None:
        inventory.expiry_date = cleaned["expiry_date"]
    if cleaned.get("minimum_stock") is not None:
        inventory.minimum_stock = cleaned["minimum_stock"]
    if cleaned.get("unit"):
        inventory.unit = cleaned["unit"]

    _sync_low_stock_alert(inventory, actor=actor)
    db.session.commit()
    return inventory


# ---------------------------------------------------------------------------
# Distributions (stock usage)
# ---------------------------------------------------------------------------
def distributions_query(
    *,
    scope_centre_id=None,
    centre_id=None,
    item_id=None,
    beneficiary_id=None,
) -> list[NutritionDistribution]:
    """Return distributions ordered newest first, with optional filters."""
    query = NutritionDistribution.query
    if scope_centre_id is not None:
        query = query.filter(NutritionDistribution.centre_id == scope_centre_id)
    elif centre_id is not None:
        query = query.filter(NutritionDistribution.centre_id == centre_id)
    if item_id is not None:
        query = query.filter(NutritionDistribution.item_id == item_id)
    if beneficiary_id is not None:
        query = query.filter(
            NutritionDistribution.beneficiary_id == beneficiary_id
        )
    return query.order_by(
        NutritionDistribution.distribution_date.desc(),
        NutritionDistribution.id.desc(),
    ).all()


def distributions_for_beneficiary(beneficiary) -> list[NutritionDistribution]:
    """Return a beneficiary's distribution history, newest first."""
    return distributions_query(beneficiary_id=beneficiary.id)


def record_distribution(
    beneficiary, item: NutritionItem, form, *, actor=None
) -> NutritionDistribution:
    """Validate and record a distribution, decrementing available stock.

    The distribution is always recorded at the beneficiary's centre.  A
    distribution larger than the current available stock is rejected.
    """
    cleaned, errors = validate_nutrition_distribution_fields(form)
    if errors:
        raise ValidationError(errors)

    centre = beneficiary.centre
    inventory = inventory_row(centre.id, item.id)
    available = inventory.available_quantity if inventory is not None else Decimal("0")
    quantity = cleaned["quantity"]

    if quantity > available:
        unit = inventory.unit if inventory is not None else item.unit
        errors["quantity"] = (
            f"Quantity cannot exceed the available stock "
            f"({available} {unit})."
        )
    if errors:
        raise ValidationError(errors)

    if inventory is None:
        inventory = _get_or_create_inventory(centre, item)

    distribution = NutritionDistribution(
        beneficiary=beneficiary,
        item=item,
        centre=centre,
        worker=actor,
        quantity=quantity,
        distribution_date=cleaned["distribution_date"],
        notes=cleaned.get("notes"),
    )
    db.session.add(distribution)

    inventory.distributed_quantity = (
        (inventory.distributed_quantity or 0) + quantity
    )

    _sync_low_stock_alert(inventory, actor=actor)
    db.session.commit()
    return distribution


# ---------------------------------------------------------------------------
# Low-stock alert synchronisation (scoped integration point for Phase 9)
# ---------------------------------------------------------------------------
def _alert_marker(centre_id: int, item_id: int) -> str:
    return f"[inventory:{centre_id}:{item_id}]"


def open_low_stock_alert(centre_id: int, item_id: int) -> Alert | None:
    """Return the current open/in-progress low-stock alert, if any."""
    marker = _alert_marker(centre_id, item_id) + " %"
    return (
        Alert.query.filter(
            Alert.alert_type == AlertType.LOW_NUTRITION_STOCK,
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.IN_PROGRESS]),
            Alert.message.like(marker),
        )
        .order_by(Alert.created_at.desc())
        .first()
    )


def _sync_low_stock_alert(inventory: Inventory, *, actor=None) -> Alert | None:
    """Create, update or resolve the low-stock alert for an inventory row."""
    existing = open_low_stock_alert(inventory.centre_id, inventory.item_id)

    if is_low_stock(inventory):
        available = inventory.available_quantity
        severity = AlertSeverity.HIGH if available <= 0 else AlertSeverity.MEDIUM
        message = (
            f"{_alert_marker(inventory.centre_id, inventory.item_id)} "
            f"Low stock: {inventory.item.name} at {inventory.centre.name} is "
            f"{available} {inventory.unit} (configured minimum "
            f"{inventory.minimum_stock})."
        )
        if existing is None:
            alert = Alert(
                alert_type=AlertType.LOW_NUTRITION_STOCK,
                severity=severity,
                message=message,
                status=AlertStatus.OPEN,
                assigned_to=actor,
                created_by=actor,
            )
            db.session.add(alert)
            return alert
        existing.severity = severity
        existing.message = message
        return existing

    if existing is not None:
        existing.status = AlertStatus.RESOLVED
        existing.resolved_at = datetime.utcnow()
        existing.resolution_notes = (
            f"Stock replenished to {inventory.available_quantity} "
            f"{inventory.unit}."
        )
    return existing


__all__ = [
    "active_centres",
    "active_items",
    "all_items",
    "create_item",
    "distributions_for_beneficiary",
    "distributions_query",
    "get_item",
    "inventory_list",
    "inventory_row",
    "is_low_stock",
    "low_stock_list",
    "open_low_stock_alert",
    "record_distribution",
    "record_stock_received",
    "summary",
    "update_item",
]
