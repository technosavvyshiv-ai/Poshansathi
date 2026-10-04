"""Phase 4 child growth tests: recording, validation, status rules, alerts."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import Alert, AnganwadiCentre, Beneficiary, Child, GrowthRecord, User
from app.services import growth_service
from app.utils.constants import (
    AlertStatus,
    AlertType,
    BeneficiaryType,
    Gender,
    NutritionalStatus,
    RecordStatus,
    UserRole,
)
from app.utils.growth_rules import GrowthDemoRules, age_in_months, classify, is_concerning

PASSWORD = "password123"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def centre(db):
    centre = AnganwadiCentre(name="Growth Centre A", code="GCA-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def other_centre(db):
    centre = AnganwadiCentre(name="Growth Centre B", code="GCB-001", is_active=True)
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
def make_child(db):
    def make(centre, name="Growth Child", dob=None):
        two_years_ago = date.today().replace(year=date.today().year - 2)
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=BeneficiaryType.CHILD,
            full_name=name,
            date_of_birth=dob or two_years_ago,
            gender=Gender.FEMALE,
            status=RecordStatus.ACTIVE,
            registration_date=date.today(),
        )
        child = Child(beneficiary=beneficiary)
        db.session.add(child)
        db.session.commit()
        return child

    return make


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


def growth_form(**overrides):
    data = {
        "measurement_date": date.today().isoformat(),
        "weight_kg": "10.0",
        "height_cm": "85.0",
        "muac_cm": "14.5",
        "notes": "Routine demo measurement.",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Rule unit tests
# ---------------------------------------------------------------------------
def test_age_in_months():
    dob = date(2024, 1, 15)
    assert age_in_months(dob, date(2024, 1, 15)) == 0
    assert age_in_months(dob, date(2024, 12, 14)) == 10
    assert age_in_months(dob, date(2025, 1, 15)) == 12
    assert age_in_months(dob, date(2025, 2, 20)) == 13
    # Before birth is clamped to zero.
    assert age_in_months(dob, date(2023, 1, 1)) == 0


@pytest.mark.parametrize(
    "weight, expected_status",
    [
        (11.0, NutritionalStatus.NORMAL),
        (10.0, NutritionalStatus.NORMAL),
        (8.5, NutritionalStatus.UNDERWEIGHT),
        (7.0, NutritionalStatus.SEVERE_UNDERWEIGHT),
        (15.0, NutritionalStatus.OVERWEIGHT),
    ],
)
def test_classify_weight_for_age(weight, expected_status):
    status, ratio = classify(weight, age_months=24)
    assert status == expected_status
    assert ratio > 0


def test_is_concerning():
    assert is_concerning(NutritionalStatus.UNDERWEIGHT) is True
    assert is_concerning(NutritionalStatus.SEVERE_UNDERWEIGHT) is True
    assert is_concerning(NutritionalStatus.NORMAL) is False
    assert is_concerning(NutritionalStatus.OVERWEIGHT) is False


def test_current_rules_default(app):
    rules = growth_service.current_rules()
    assert rules.expected_weight(24) == 11.0


def test_current_rules_can_be_configured(app):
    custom = GrowthDemoRules(
        expected_weight_kg=((72, 10.0),),
        severe_ratio=0.5,
        under_ratio=0.6,
        over_ratio=1.5,
    )
    app.config["GROWTH_DEMO_RULES"] = custom

    assert growth_service.current_rules() is custom

    status, _ = classify(9.0, age_months=24, rules=custom)
    assert status == NutritionalStatus.NORMAL


# ---------------------------------------------------------------------------
# Create / history
# ---------------------------------------------------------------------------
def test_aww_can_record_growth(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")

    response = client.post(
        f"/children/{child.id}/growth/new", data=growth_form(weight_kg="10.0")
    )

    assert response.status_code == 302
    record = GrowthRecord.query.filter_by(child_id=child.id).one()
    assert record.nutritional_status == NutritionalStatus.NORMAL
    assert record.recorded_by is not None
    assert response.headers["Location"].endswith(f"/children/{child.id}/growth")


def test_history_page_renders(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")
    client.post(f"/children/{child.id}/growth/new", data=growth_form())

    response = client.get(f"/children/{child.id}/growth")

    assert response.status_code == 200
    assert b"Growth history" in response.data
    assert b"Growth Child" in response.data
    assert b"growth-chart-data" in response.data


def test_growth_view_shows_demo_rule_disclaimer(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")
    client.post(f"/children/{child.id}/growth/new", data=growth_form())

    response = client.get(f"/children/{child.id}/growth")

    assert b"demonstration rule" in response.data.lower()
    assert b"not an official growth reference" in response.data.lower()


def test_history_is_newest_first(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")
    older = date.today() - timedelta(days=30)
    client.post(f"/children/{child.id}/growth/new", data=growth_form(measurement_date=older.isoformat()))
    client.post(f"/children/{child.id}/growth/new", data=growth_form())

    history = growth_service.build_history(child)

    assert history[0]["record"].measurement_date == date.today()
    assert history[1]["record"].measurement_date == older


def test_chart_data_series(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")
    client.post(
        f"/children/{child.id}/growth/new",
        data=growth_form(measurement_date=(date.today() - timedelta(days=30)).isoformat()),
    )
    client.post(f"/children/{child.id}/growth/new", data=growth_form())

    data = growth_service.chart_data(child)

    assert len(data["labels"]) == 2
    assert data["weight"] == [10.0, 10.0]
    assert data["height"] == [85.0, 85.0]


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
def test_edit_growth_record_reclassifies(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")
    client.post(f"/children/{child.id}/growth/new", data=growth_form(weight_kg="10.0"))
    record = GrowthRecord.query.filter_by(child_id=child.id).one()

    response = client.post(
        f"/children/{child.id}/growth/{record.id}/edit",
        data=growth_form(weight_kg="7.0"),
    )

    assert response.status_code == 302
    db.session.refresh(record)
    assert record.weight_kg == 7.0
    assert record.nutritional_status == NutritionalStatus.SEVERE_UNDERWEIGHT


def test_edit_form_is_prefilled(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")
    client.post(f"/children/{child.id}/growth/new", data=growth_form(weight_kg="10.0"))
    record = GrowthRecord.query.filter_by(child_id=child.id).one()

    response = client.get(f"/children/{child.id}/growth/{record.id}/edit")

    assert response.status_code == 200
    assert b'value="10.00"' in response.data or b'value="10.0"' in response.data


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "override, expected",
    [
        ({"measurement_date": ""}, b"Measurement date is required"),
        (
            {"measurement_date": (date.today() + timedelta(days=1)).isoformat()},
            b"cannot be in the future",
        ),
        ({"weight_kg": ""}, b"Weight (kg) is required"),
        ({"weight_kg": "0.1"}, b"at least"),
        ({"height_cm": "500"}, b"at most"),
        ({"muac_cm": "1"}, b"at least"),
    ],
)
def test_growth_validation_errors(
    client, db, centre, make_user, make_child, override, expected
):
    child = make_child(centre)
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")

    response = client.post(
        f"/children/{child.id}/growth/new", data=growth_form(**override)
    )

    assert response.status_code == 400
    assert expected in response.data
    assert GrowthRecord.query.count() == 0


def test_measurement_before_birth_rejected(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")

    response = client.post(
        f"/children/{child.id}/growth/new",
        data=growth_form(
            measurement_date=(date.today() - timedelta(days=2 * 365 + 10)).isoformat()
        ),
    )

    assert response.status_code == 400
    assert b"before the child" in response.data


def test_duplicate_measurement_date_rejected(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")
    client.post(f"/children/{child.id}/growth/new", data=growth_form())

    response = client.post(f"/children/{child.id}/growth/new", data=growth_form())

    assert response.status_code == 400
    assert b"already exists" in response.data
    assert GrowthRecord.query.count() == 1


# ---------------------------------------------------------------------------
# Growth alert synchronisation
# ---------------------------------------------------------------------------
def test_concerning_growth_creates_follow_up_alert(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")

    client.post(f"/children/{child.id}/growth/new", data=growth_form(weight_kg="7.0"))

    alert = Alert.query.filter_by(child_id=child.id).one()
    assert alert.alert_type == AlertType.GROWTH_FOLLOW_UP
    assert alert.status == AlertStatus.OPEN
    assert alert.severity.value == "HIGH"


def test_later_normal_growth_resolves_open_alert(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")

    client.post(
        f"/children/{child.id}/growth/new",
        data=growth_form(
            measurement_date=(date.today() - timedelta(days=30)).isoformat(),
            weight_kg="7.0",
        ),
    )
    assert growth_service.open_growth_alert(child) is not None

    client.post(f"/children/{child.id}/growth/new", data=growth_form(weight_kg="10.0"))

    assert growth_service.open_growth_alert(child) is None
    resolved = Alert.query.filter_by(child_id=child.id, status=AlertStatus.RESOLVED).all()
    assert len(resolved) == 1


def test_normal_growth_does_not_create_alert(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")

    client.post(f"/children/{child.id}/growth/new", data=growth_form(weight_kg="10.0"))

    assert Alert.query.count() == 0


# ---------------------------------------------------------------------------
# Role permissions / centre scoping
# ---------------------------------------------------------------------------
def test_growth_requires_login(client, db, centre, make_child):
    child = make_child(centre)
    response = client.get(f"/children/{child.id}/growth")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize("role", [UserRole.SUPERVISOR, UserRole.OFFICER])
def test_read_only_roles_cannot_record_growth(
    client, db, centre, make_user, make_child, role
):
    child = make_child(centre)
    make_user("reader", role=role)
    login(client, "reader")

    response = client.post(
        f"/children/{child.id}/growth/new", data=growth_form()
    )

    assert response.status_code == 403


@pytest.mark.parametrize("role", [UserRole.SUPERVISOR, UserRole.OFFICER])
def test_read_only_roles_can_view_growth(
    client, db, centre, make_user, make_child, role
):
    child = make_child(centre)
    make_user("reader", role=role)
    login(client, "reader")

    response = client.get(f"/children/{child.id}/growth")

    assert response.status_code == 200


def test_aww_cannot_access_other_centres_child(
    client, db, centre, other_centre, make_user, make_child
):
    child = make_child(other_centre, name="Other Child")
    make_user("aww_growth", role=UserRole.AWW, centre=centre)
    login(client, "aww_growth")

    assert client.get(f"/children/{child.id}/growth").status_code == 403
    assert (
        client.post(
            f"/children/{child.id}/growth/new", data=growth_form()
        ).status_code
        == 403
    )
