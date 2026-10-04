"""Phase 6 maternal health tests: records, history, edit, validation, access."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import (
    AnganwadiCentre,
    Beneficiary,
    MaternalHealthRecord,
    Mother,
    User,
)
from app.services import maternal_service
from app.utils.constants import (
    BeneficiaryType,
    Gender,
    RecordStatus,
    RiskLevel,
    UserRole,
)
from app.utils.maternal_rules import (
    FollowUpStatus,
    follow_up_status,
    risk_badge,
    risk_label,
)

PASSWORD = "password123"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def centre(db):
    centre = AnganwadiCentre(name="Maternal Centre A", code="MCA-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def other_centre(db):
    centre = AnganwadiCentre(name="Maternal Centre B", code="MCB-001", is_active=True)
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
def make_mother(db):
    def make(
        centre,
        name="Maternal Mother",
        dob=None,
        beneficiary_type=BeneficiaryType.PREGNANT_WOMAN,
        lmp="default",
    ):
        if lmp == "default":
            lmp = date.today() - timedelta(days=100)
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=beneficiary_type,
            full_name=name,
            date_of_birth=dob or date(1995, 1, 1),
            gender=Gender.FEMALE,
            status=RecordStatus.ACTIVE,
            registration_date=date.today(),
        )
        mother = Mother(
            beneficiary=beneficiary,
            age=30,
            last_menstrual_period=lmp,
            current_risk_level=RiskLevel.LOW,
        )
        db.session.add(mother)
        db.session.commit()
        return mother

    return make


@pytest.fixture()
def make_record(db):
    def make(mother, **overrides):
        data = {
            "visit_date": date.today(),
            "pregnancy_month": 5,
            "weight_kg": 58.5,
            "haemoglobin": 11.2,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "risk_category": RiskLevel.LOW,
            "next_follow_up_date": date.today() + timedelta(days=30),
            "notes": "Stored ANC record.",
        }
        data.update(overrides)
        record = MaternalHealthRecord(mother=mother, **data)
        db.session.add(record)
        db.session.commit()
        return record

    return make


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


def maternal_form(**overrides):
    data = {
        "visit_date": date.today().isoformat(),
        "pregnancy_month": "5",
        "weight_kg": "58.5",
        "haemoglobin": "11.2",
        "systolic_bp": "120",
        "diastolic_bp": "80",
        "risk_category": "LOW",
        "next_follow_up_date": (date.today() + timedelta(days=30)).isoformat(),
        "notes": "Routine ANC visit.",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Display-rule unit tests
# ---------------------------------------------------------------------------
class _Record:
    """Stand-in so display rules can be tested without the database."""

    def __init__(self, next_follow_up_date=None, risk_category=None):
        self.next_follow_up_date = next_follow_up_date
        self.risk_category = risk_category


def test_follow_up_status_is_derived_from_stored_date():
    today = date(2026, 6, 10)
    assert (
        follow_up_status(_Record(None), today) == FollowUpStatus.NONE
    )
    assert (
        follow_up_status(_Record(today - timedelta(days=1)), today)
        == FollowUpStatus.OVERDUE
    )
    assert (
        follow_up_status(_Record(today), today) == FollowUpStatus.DUE
    )
    assert (
        follow_up_status(_Record(today + timedelta(days=1)), today)
        == FollowUpStatus.UPCOMING
    )


def test_risk_label_and_badge():
    assert risk_label(RiskLevel.LOW) == "Low"
    assert risk_label(RiskLevel.HIGH) == "High"
    assert risk_badge(RiskLevel.HIGH) == "text-bg-danger"
    assert risk_label(None) == "—"


# ---------------------------------------------------------------------------
# Create / history
# ---------------------------------------------------------------------------
def test_aww_can_record_maternal_health(client, db, centre, make_user, make_mother):
    mother = make_mother(centre)
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")

    response = client.post(
        f"/mothers/{mother.id}/health/new", data=maternal_form()
    )

    assert response.status_code == 302
    record = MaternalHealthRecord.query.filter_by(mother_id=mother.id).one()
    assert record.pregnancy_month == 5
    assert record.risk_category == RiskLevel.LOW
    assert record.recorded_by is not None
    assert response.headers["Location"].endswith(f"/mothers/{mother.id}/health")


def test_admin_can_record_maternal_health(client, db, centre, make_user, make_mother):
    mother = make_mother(centre)
    make_user("admin_mat", role=UserRole.ADMIN)
    login(client, "admin_mat")

    response = client.post(
        f"/mothers/{mother.id}/health/new", data=maternal_form()
    )

    assert response.status_code == 302
    assert MaternalHealthRecord.query.count() == 1


def test_history_page_renders(client, db, centre, make_user, make_mother):
    mother = make_mother(centre)
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")
    client.post(f"/mothers/{mother.id}/health/new", data=maternal_form())

    response = client.get(f"/mothers/{mother.id}/health")

    assert response.status_code == 200
    assert b"Maternal Health" in response.data
    assert b"ANC visit history" in response.data
    assert b"Maternal Mother" in response.data
    assert b"Low" in response.data


def test_history_empty_state(client, db, centre, make_user, make_mother):
    mother = make_mother(centre)
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")

    response = client.get(f"/mothers/{mother.id}/health")

    assert response.status_code == 200
    assert b"No ANC records found" in response.data


def test_history_shows_demo_disclaimer(client, db, centre, make_user, make_mother):
    mother = make_mother(centre)
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")
    client.post(f"/mothers/{mother.id}/health/new", data=maternal_form())

    response = client.get(f"/mothers/{mother.id}/health")

    assert b"project-defined demo view" in response.data.lower()
    assert b"not medical guidance" in response.data.lower()
    assert b"does not make clinical" in response.data.lower()


def test_summary_and_pending_follow_up_prefers_overdue(
    client, db, centre, make_user, make_mother, make_record
):
    mother = make_mother(centre)
    make_record(
        mother,
        visit_date=date.today() - timedelta(days=60),
        next_follow_up_date=date.today() - timedelta(days=5),
    )
    make_record(
        mother,
        visit_date=date.today() - timedelta(days=10),
        next_follow_up_date=date.today() + timedelta(days=20),
    )

    data = maternal_service.summary(mother)

    assert data["total"] == 2
    follow = data["pending_follow_up"]
    assert follow is not None
    assert follow["status"] == FollowUpStatus.OVERDUE.value
    assert follow["overdue"] is True
    assert follow["date"] == date.today() - timedelta(days=5)


def test_history_is_newest_first(
    client, db, centre, make_user, make_mother, make_record
):
    mother = make_mother(centre)
    older = date.today() - timedelta(days=40)
    make_record(mother, visit_date=older)
    make_record(mother, visit_date=date.today())

    history = maternal_service.build_history(mother)

    assert history[0]["record"].visit_date == date.today()
    assert history[1]["record"].visit_date == older


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
def test_edit_maternal_record(client, db, centre, make_user, make_mother, make_record):
    mother = make_mother(centre)
    record = make_record(mother)
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")

    response = client.post(
        f"/mothers/{mother.id}/health/{record.id}/edit",
        data=maternal_form(
            risk_category="HIGH",
            haemoglobin="8.5",
            notes="Updated by test.",
        ),
    )

    assert response.status_code == 302
    db.session.refresh(record)
    assert record.risk_category == RiskLevel.HIGH
    assert str(record.haemoglobin) == "8.5"
    assert record.notes == "Updated by test."


def test_edit_form_is_prefilled(
    client, db, centre, make_user, make_mother, make_record
):
    mother = make_mother(centre)
    record = make_record(mother, pregnancy_month=7, notes="Original note")
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")

    response = client.get(f"/mothers/{mother.id}/health/{record.id}/edit")

    assert response.status_code == 200
    assert b'value="7"' in response.data
    assert b"Original note" in response.data


def test_edit_record_of_another_mother_is_404(
    client, db, centre, make_user, make_mother, make_record
):
    mother = make_mother(centre, name="Mother One")
    other = make_mother(centre, name="Mother Two")
    record = make_record(other)
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")

    response = client.get(
        f"/mothers/{mother.id}/health/{record.id}/edit"
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "override, expected",
    [
        ({"visit_date": ""}, b"ANC visit date is required"),
        (
            {"visit_date": (date.today() + timedelta(days=1)).isoformat()},
            b"cannot be in the future",
        ),
        ({"pregnancy_month": "0"}, b"at least"),
        ({"pregnancy_month": "13"}, b"at most"),
        ({"weight_kg": "10"}, b"at least"),
        ({"haemoglobin": "25"}, b"at most"),
        ({"systolic_bp": "300"}, b"at most"),
        ({"diastolic_bp": "200"}, b"at most"),
        (
            {"systolic_bp": "110", "diastolic_bp": "120"},
            b"lower than systolic",
        ),
        ({"risk_category": ""}, b"Risk category is required"),
        (
            {"next_follow_up_date": (date.today() - timedelta(days=1)).isoformat()},
            b"before the ANC visit date",
        ),
    ],
)
def test_maternal_validation_errors(
    client, db, centre, make_user, make_mother, override, expected
):
    mother = make_mother(centre)
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")

    response = client.post(
        f"/mothers/{mother.id}/health/new", data=maternal_form(**override)
    )

    assert response.status_code == 400
    assert expected in response.data
    assert MaternalHealthRecord.query.count() == 0


def test_visit_before_last_menstrual_period_rejected(
    client, db, centre, make_user, make_mother
):
    mother = make_mother(centre, lmp=date.today() - timedelta(days=100))
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")

    response = client.post(
        f"/mothers/{mother.id}/health/new",
        data=maternal_form(
            visit_date=(date.today() - timedelta(days=150)).isoformat()
        ),
    )

    assert response.status_code == 400
    assert b"before the last menstrual period" in response.data


def test_visit_before_birth_rejected(client, db, centre, make_user, make_mother):
    mother = make_mother(centre, dob=date(1995, 1, 1), lmp=None)
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")

    response = client.post(
        f"/mothers/{mother.id}/health/new",
        data=maternal_form(visit_date=date(1990, 1, 1).isoformat()),
    )

    assert response.status_code == 400
    assert b"before the mother" in response.data


# ---------------------------------------------------------------------------
# Duplicate handling
# ---------------------------------------------------------------------------
def test_duplicate_visit_date_rejected(
    client, db, centre, make_user, make_mother
):
    mother = make_mother(centre)
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")
    client.post(f"/mothers/{mother.id}/health/new", data=maternal_form())

    response = client.post(
        f"/mothers/{mother.id}/health/new", data=maternal_form()
    )

    assert response.status_code == 400
    assert b"already exists" in response.data
    assert MaternalHealthRecord.query.count() == 1


def test_edit_into_duplicate_rejected(
    client, db, centre, make_user, make_mother, make_record
):
    mother = make_mother(centre)
    make_record(mother, visit_date=date.today())
    record = make_record(
        mother, visit_date=date.today() - timedelta(days=5)
    )
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")

    response = client.post(
        f"/mothers/{mother.id}/health/{record.id}/edit",
        data=maternal_form(visit_date=date.today().isoformat()),
    )

    assert response.status_code == 400
    assert b"already exists" in response.data
    assert MaternalHealthRecord.query.count() == 2


# ---------------------------------------------------------------------------
# Role permissions / centre scoping
# ---------------------------------------------------------------------------
def test_maternal_requires_login(client, db, centre, make_mother):
    mother = make_mother(centre)
    response = client.get(f"/mothers/{mother.id}/health")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize("role", [UserRole.SUPERVISOR, UserRole.OFFICER])
def test_read_only_roles_can_view_but_not_modify(
    client, db, centre, make_user, make_mother, role
):
    mother = make_mother(centre)
    make_user("reader", role=role)
    login(client, "reader")

    assert client.get(f"/mothers/{mother.id}/health").status_code == 200
    assert (
        client.post(
            f"/mothers/{mother.id}/health/new", data=maternal_form()
        ).status_code
        == 403
    )
    assert MaternalHealthRecord.query.count() == 0


def test_aww_cannot_access_other_centres_mother(
    client, db, centre, other_centre, make_user, make_mother, make_record
):
    mother = make_mother(other_centre, name="Other Centre Mother")
    record = make_record(mother)
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")

    assert client.get(f"/mothers/{mother.id}/health").status_code == 403
    assert (
        client.post(
            f"/mothers/{mother.id}/health/new", data=maternal_form()
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/mothers/{mother.id}/health/{record.id}/edit"
        ).status_code
        == 403
    )


# ---------------------------------------------------------------------------
# Beneficiary profile integration
# ---------------------------------------------------------------------------
def test_mother_profile_links_to_maternal_health(
    client, db, centre, make_user, make_mother
):
    mother = make_mother(centre)
    make_user("aww_mat", role=UserRole.AWW, centre=centre)
    login(client, "aww_mat")

    response = client.get(f"/beneficiaries/{mother.beneficiary_id}")

    assert response.status_code == 200
    assert b"View ANC visit history" in response.data
    assert f"/mothers/{mother.id}/health".encode() in response.data
