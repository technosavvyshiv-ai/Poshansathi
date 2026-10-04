"""Phase 7 nutrition tests: inventory calculations, stock, distributions, alerts."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    Alert,
    AnganwadiCentre,
    Beneficiary,
    Child,
    Inventory,
    NutritionDistribution,
    NutritionItem,
    User,
)
from app.services import nutrition_service
from app.utils.constants import (
    AlertStatus,
    AlertType,
    BeneficiaryType,
    Gender,
    RecordStatus,
    UserRole,
)

PASSWORD = "password123"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def centre(db):
    centre = AnganwadiCentre(name="Nutrition Centre A", code="NCA-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def other_centre(db):
    centre = AnganwadiCentre(name="Nutrition Centre B", code="NCB-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def make_user(db):
    def make(username, role=UserRole.AWW, centre=None):
        user = User(
            full_name=f"Test {username}",
            username=username,
            role=role,
            centre=centre,
            is_active=True,
        )
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        return user

    return make


@pytest.fixture()
def make_item(db):
    def make(name="Take Home Ration", unit="kg", **overrides):
        item = NutritionItem(name=name, unit=unit, is_active=True, **overrides)
        db.session.add(item)
        db.session.commit()
        return item

    return make


@pytest.fixture()
def make_beneficiary(db):
    def make(centre, name="Nutrition Beneficiary", beneficiary_type=BeneficiaryType.CHILD):
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=beneficiary_type,
            full_name=name,
            date_of_birth=date(2022, 1, 1),
            gender=Gender.FEMALE,
            status=RecordStatus.ACTIVE,
            registration_date=date.today(),
        )
        db.session.add(beneficiary)
        db.session.commit()
        return beneficiary

    return make


@pytest.fixture()
def make_inventory(db):
    def make(
        centre,
        item,
        opening=0,
        received=0,
        distributed=0,
        minimum=0,
        unit=None,
        expiry_date=None,
        received_date=None,
    ):
        inventory = Inventory(
            centre=centre,
            item=item,
            opening_stock=Decimal(str(opening)),
            received_quantity=Decimal(str(received)),
            distributed_quantity=Decimal(str(distributed)),
            minimum_stock=Decimal(str(minimum)),
            unit=unit or item.unit,
            expiry_date=expiry_date,
            received_date=received_date,
        )
        db.session.add(inventory)
        db.session.commit()
        return inventory

    return make


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


def item_form(**overrides):
    data = {"name": "Fortified Atta", "category": "Ration", "unit": "kg", "is_active": "on"}
    data.update(overrides)
    return data


def stock_form(**overrides):
    data = {
        "quantity": "50",
        "received_date": date.today().isoformat(),
        "minimum_stock": "20",
        "unit": "kg",
    }
    data.update(overrides)
    return data


def distribution_form(item, beneficiary, **overrides):
    data = {
        "item_id": str(item),
        "beneficiary_id": str(beneficiary),
        "quantity": "5",
        "distribution_date": date.today().isoformat(),
        "notes": "Routine demo distribution.",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Inventory calculation unit tests
# ---------------------------------------------------------------------------
def test_available_quantity_is_opening_received_distributed(
    db, centre, make_item, make_inventory
):
    item = make_item()
    inventory = make_inventory(
        centre, item, opening=10, received=30, distributed=5, minimum=20
    )

    assert inventory.available_quantity == Decimal("35")
    assert inventory.is_low_stock is False
    assert nutrition_service.is_low_stock(inventory) is False


def test_low_stock_requires_a_configured_minimum(
    db, centre, make_item, make_inventory
):
    zero_item = make_item(name="Zero Minimum Item")
    zero_min = make_inventory(centre, zero_item, received=0, distributed=0, minimum=0)
    assert zero_min.is_low_stock is True  # 0 <= 0
    assert nutrition_service.is_low_stock(zero_min) is False  # not configured

    configured_item = make_item(name="Configured Minimum Item")
    configured = make_inventory(
        centre, configured_item, received=10, distributed=0, minimum=10
    )
    assert nutrition_service.is_low_stock(configured) is True


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------
def test_admin_can_create_item(client, db, make_user):
    make_user("admin_nut", role=UserRole.ADMIN)
    login(client, "admin_nut")

    response = client.post("/nutrition/items/new", data=item_form())

    assert response.status_code == 302
    assert NutritionItem.query.filter_by(name="Fortified Atta").count() == 1


def test_aww_cannot_create_item(client, db, centre, make_user):
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    response = client.post("/nutrition/items/new", data=item_form())

    assert response.status_code == 403
    assert NutritionItem.query.count() == 0


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"name": ""}, b"Item name is required"),
        ({"unit": ""}, b"Unit is required"),
    ],
)
def test_item_validation(client, db, make_user, override, expected):
    make_user("admin_nut", role=UserRole.ADMIN)
    login(client, "admin_nut")

    response = client.post("/nutrition/items/new", data=item_form(**override))

    assert response.status_code == 400
    assert expected in response.data
    assert NutritionItem.query.count() == 0


def test_duplicate_item_name_rejected(client, db, make_user):
    make_user("admin_nut", role=UserRole.ADMIN)
    login(client, "admin_nut")
    client.post("/nutrition/items/new", data=item_form(name="Fortified Atta"))

    response = client.post(
        "/nutrition/items/new", data=item_form(name="fortified atta")
    )

    assert response.status_code == 400
    assert b"already exists" in response.data
    assert NutritionItem.query.count() == 1


# ---------------------------------------------------------------------------
# Stock received
# ---------------------------------------------------------------------------
def test_aww_can_record_stock(client, db, centre, make_user, make_item):
    item = make_item()
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    response = client.post(
        "/nutrition/stock/new",
        data=stock_form(item_id=str(item.id), quantity="40", minimum_stock="15"),
    )

    assert response.status_code == 302
    inventory = Inventory.query.filter_by(centre_id=centre.id, item_id=item.id).one()
    assert inventory.received_quantity == Decimal("40")


def test_record_stock_creates_inventory_and_sets_dates(
    client, db, centre, make_user, make_item
):
    item = make_item(unit="kg")
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    response = client.post(
        "/nutrition/stock/new",
        data=stock_form(
            item_id=str(item.id),
            quantity="40",
            minimum_stock="15",
            received_date=date.today().isoformat(),
            expiry_date=(date.today() + timedelta(days=90)).isoformat(),
        ),
        follow_redirects=False,
    )

    assert response.status_code == 302
    inventory = Inventory.query.filter_by(centre_id=centre.id, item_id=item.id).one()
    assert inventory.received_quantity == Decimal("40")
    assert inventory.minimum_stock == Decimal("15")
    assert inventory.unit == "kg"
    assert inventory.expiry_date == date.today() + timedelta(days=90)


def test_admin_can_record_stock_for_a_centre(client, db, centre, make_user, make_item):
    item = make_item()
    make_user("admin_nut", role=UserRole.ADMIN)
    login(client, "admin_nut")

    response = client.post(
        "/nutrition/stock/new",
        data=stock_form(item_id=str(item.id), centre_id=str(centre.id)),
    )

    assert response.status_code == 302
    assert Inventory.query.filter_by(centre_id=centre.id, item_id=item.id).count() == 1


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"quantity": ""}, b"Received quantity is required"),
        ({"quantity": "0"}, b"at least"),
    ],
)
def test_stock_validation(client, db, centre, make_user, make_item, override, expected):
    item = make_item()
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    response = client.post(
        "/nutrition/stock/new",
        data=stock_form(item_id=str(item.id), **override),
    )

    assert response.status_code == 400
    assert expected in response.data
    assert Inventory.query.count() == 0


def test_expiry_before_received_rejected(client, db, centre, make_user, make_item):
    item = make_item()
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    response = client.post(
        "/nutrition/stock/new",
        data=stock_form(
            item_id=str(item.id),
            received_date=date.today().isoformat(),
            expiry_date=(date.today() - timedelta(days=1)).isoformat(),
        ),
    )

    assert response.status_code == 400
    assert b"before the received date" in response.data


# ---------------------------------------------------------------------------
# Distributions
# ---------------------------------------------------------------------------
def test_aww_can_record_distribution(
    client, db, centre, make_user, make_item, make_beneficiary, make_inventory
):
    item = make_item()
    beneficiary = make_beneficiary(centre)
    make_inventory(centre, item, received=100, minimum=10)
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    response = client.post(
        "/nutrition/distributions/new",
        data=distribution_form(item.id, beneficiary.id, quantity="8"),
    )

    assert response.status_code == 302
    distribution = NutritionDistribution.query.filter_by(
        beneficiary_id=beneficiary.id
    ).one()
    assert distribution.quantity == Decimal("8")
    assert distribution.worker is not None
    inventory = Inventory.query.filter_by(centre_id=centre.id, item_id=item.id).one()
    assert inventory.distributed_quantity == Decimal("8")
    assert inventory.available_quantity == Decimal("92")


def test_distribution_exceeding_stock_rejected(
    client, db, centre, make_user, make_item, make_beneficiary, make_inventory
):
    item = make_item()
    beneficiary = make_beneficiary(centre)
    make_inventory(centre, item, received=5)
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    response = client.post(
        "/nutrition/distributions/new",
        data=distribution_form(item.id, beneficiary.id, quantity="10"),
    )

    assert response.status_code == 400
    assert b"cannot exceed the available stock" in response.data
    assert NutritionDistribution.query.count() == 0
    inventory = Inventory.query.filter_by(centre_id=centre.id, item_id=item.id).one()
    assert inventory.distributed_quantity == Decimal("0")


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"item_id": ""}, b"Please select a nutrition item"),
        ({"quantity": ""}, b"Quantity is required"),
        ({"quantity": "0"}, b"at least"),
        (
            {"distribution_date": (date.today() + timedelta(days=1)).isoformat()},
            b"cannot be in the future",
        ),
    ],
)
def test_distribution_validation(
    client, db, centre, make_user, make_item, make_beneficiary, make_inventory,
    override, expected,
):
    item = make_item()
    beneficiary = make_beneficiary(centre)
    make_inventory(centre, item, received=100)
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    data = distribution_form(item.id, beneficiary.id, **override)
    response = client.post("/nutrition/distributions/new", data=data)

    assert response.status_code == 400
    assert expected in response.data
    assert NutritionDistribution.query.count() == 0


def test_distribution_history_page(
    client, db, centre, make_user, make_item, make_beneficiary, make_inventory
):
    item = make_item(name="Groundnut Chikki")
    beneficiary = make_beneficiary(centre)
    make_inventory(centre, item, received=50)
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")
    client.post(
        "/nutrition/distributions/new",
        data=distribution_form(item.id, beneficiary.id, quantity="3"),
    )

    response = client.get("/nutrition/distributions")

    assert response.status_code == 200
    assert b"Nutrition distribution history" in response.data
    assert b"Groundnut Chikki" in response.data
    assert b"Nutrition Beneficiary" in response.data


def test_beneficiary_nutrition_history(
    client, db, centre, make_user, make_item, make_beneficiary, make_inventory
):
    item = make_item(name="Ready to Eat")
    beneficiary = make_beneficiary(centre)
    make_inventory(centre, item, received=50)
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")
    client.post(
        "/nutrition/distributions/new",
        data=distribution_form(item.id, beneficiary.id, quantity="4"),
    )

    response = client.get(f"/beneficiaries/{beneficiary.id}/nutrition")

    assert response.status_code == 200
    assert b"Nutrition history" in response.data
    assert b"Ready to Eat" in response.data


# ---------------------------------------------------------------------------
# Low-stock tracking
# ---------------------------------------------------------------------------
def test_low_stock_alert_created_and_resolved(
    client, db, centre, make_user, make_item, make_beneficiary, make_inventory
):
    item = make_item()
    beneficiary = make_beneficiary(centre)
    make_inventory(centre, item, received=100, minimum=50)
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    # Distribution drops available to 40 <= minimum 50 -> low stock alert.
    client.post(
        "/nutrition/distributions/new",
        data=distribution_form(item.id, beneficiary.id, quantity="60"),
    )

    alert = nutrition_service.open_low_stock_alert(centre.id, item.id)
    assert alert is not None
    assert alert.alert_type == AlertType.LOW_NUTRITION_STOCK
    assert alert.status == AlertStatus.OPEN
    assert f"[inventory:{centre.id}:{item.id}]" in alert.message

    # Replenish -> alert resolved.
    client.post(
        "/nutrition/stock/new",
        data=stock_form(item_id=str(item.id), quantity="100", minimum_stock="50"),
    )

    assert nutrition_service.open_low_stock_alert(centre.id, item.id) is None
    resolved = Alert.query.filter_by(
        alert_type=AlertType.LOW_NUTRITION_STOCK, status=AlertStatus.RESOLVED
    ).all()
    assert len(resolved) == 1


def test_low_stock_highlighted_on_index(
    client, db, centre, make_user, make_item, make_inventory
):
    item = make_item(name="Chana Dal")
    make_inventory(centre, item, received=5, minimum=25)
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    response = client.get("/nutrition/")

    assert response.status_code == 200
    assert b"Low stock" in response.data
    assert b"Chana Dal" in response.data


# ---------------------------------------------------------------------------
# Permissions / centre scoping
# ---------------------------------------------------------------------------
def test_nutrition_requires_login(client, db):
    response = client.get("/nutrition/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize("role", [UserRole.SUPERVISOR, UserRole.OFFICER])
def test_read_only_roles_cannot_write(client, db, centre, make_user, role):
    make_user("reader", role=role)
    login(client, "reader")

    assert client.get("/nutrition/").status_code == 200
    assert client.post("/nutrition/stock/new", data=stock_form()).status_code == 403
    assert (
        client.post("/nutrition/distributions/new", data=distribution_form(1, 1)).status_code
        == 403
    )


def test_aww_cannot_distribute_to_other_centres_beneficiary(
    client, db, centre, other_centre, make_user, make_item, make_beneficiary
):
    item = make_item()
    other = make_beneficiary(other_centre, name="Other Centre Person")
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    response = client.post(
        "/nutrition/distributions/new",
        data=distribution_form(item.id, other.id),
    )

    assert response.status_code == 403
    assert NutritionDistribution.query.count() == 0


def test_aww_cannot_view_other_centres_beneficiary_history(
    client, db, centre, other_centre, make_user, make_beneficiary
):
    other = make_beneficiary(other_centre, name="Other Centre Person")
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    assert client.get(f"/beneficiaries/{other.id}/nutrition").status_code == 403


def test_aww_index_is_centre_scoped(
    client, db, centre, other_centre, make_user, make_item, make_inventory
):
    own_item = make_item(name="Own Item")
    other_item = make_item(name="Other Item")
    make_inventory(centre, own_item, received=5, minimum=25)
    make_inventory(other_centre, other_item, received=5, minimum=25)
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    response = client.get("/nutrition/")

    assert response.status_code == 200
    assert b"Nutrition Centre A" in response.data
    assert b"Nutrition Centre B" not in response.data


# ---------------------------------------------------------------------------
# Beneficiary profile integration
# ---------------------------------------------------------------------------
def test_beneficiary_profile_links_to_nutrition(
    client, db, centre, make_user, make_beneficiary
):
    beneficiary = make_beneficiary(centre)
    beneficiary.child = Child()
    db.session.commit()
    make_user("aww_nut", role=UserRole.AWW, centre=centre)
    login(client, "aww_nut")

    response = client.get(f"/beneficiaries/{beneficiary.id}")

    assert response.status_code == 200
    assert b"View nutrition distribution history" in response.data
    assert f"/beneficiaries/{beneficiary.id}/nutrition".encode() in response.data
