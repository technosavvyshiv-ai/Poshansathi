"""Phase 8 attendance tests: recording, editing, summaries, permissions."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import AnganwadiCentre, Attendance, Beneficiary, Child, User
from app.services import attendance_service
from app.utils.constants import (
    AttendanceStatus,
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
    centre = AnganwadiCentre(name="Attendance Centre A", code="ACA-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def other_centre(db):
    centre = AnganwadiCentre(name="Attendance Centre B", code="ACB-001", is_active=True)
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
    def make(centre, name="Attendance Child", dob=None):
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


@pytest.fixture()
def make_attendance(db):
    def make(child, on_date=None, status=AttendanceStatus.PRESENT, note=None):
        record = Attendance(
            child=child,
            centre=child.beneficiary.centre,
            attendance_date=on_date or date.today(),
            status=status,
            note=note,
        )
        db.session.add(record)
        db.session.commit()
        return record

    return make


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


def attendance_form(**overrides):
    data = {
        "attendance_date": date.today().isoformat(),
        "status": "PRESENT",
        "note": "Routine demo attendance.",
    }
    data.update(overrides)
    return data


def daily_form(centre, children, **overrides):
    """Build a bulk daily-register submission for ``children`` (all present)."""
    data = {
        "centre_id": str(centre.id),
        "attendance_date": date.today().isoformat(),
    }
    for index, child in enumerate(children):
        data[f"status_{child.id}"] = "PRESENT" if index % 2 == 0 else "ABSENT"
        data[f"note_{child.id}"] = ""
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Summary unit tests
# ---------------------------------------------------------------------------
def test_summary_calculations(db, centre, make_child, make_attendance):
    child = make_child(centre)
    make_attendance(child, date.today(), AttendanceStatus.PRESENT)
    make_attendance(child, date.today() - timedelta(days=1), AttendanceStatus.PRESENT)
    make_attendance(child, date.today() - timedelta(days=2), AttendanceStatus.PRESENT)
    make_attendance(child, date.today() - timedelta(days=3), AttendanceStatus.ABSENT)

    summary = attendance_service.child_summary(child)
    assert summary["present"] == 3
    assert summary["absent"] == 1
    assert summary["total"] == 4
    assert summary["attendance_percentage"] == 75.0


def test_monthly_summary_is_month_scoped(db, centre, make_child, make_attendance):
    child = make_child(centre)
    this_month = date.today()
    last_month = (this_month.replace(day=1) - timedelta(days=1))
    make_attendance(child, this_month, AttendanceStatus.PRESENT)
    make_attendance(child, last_month, AttendanceStatus.ABSENT)

    summary = attendance_service.monthly_summary(child, this_month.year, this_month.month)
    assert summary["total"] == 1
    assert summary["present"] == 1
    assert summary["absent"] == 0


def test_percentage_none_when_no_records(db, centre, make_child):
    child = make_child(centre)
    assert attendance_service.child_summary(child)["attendance_percentage"] is None


# ---------------------------------------------------------------------------
# Recording (create)
# ---------------------------------------------------------------------------
def test_aww_can_record_attendance(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.post(
        f"/children/{child.id}/attendance/new", data=attendance_form()
    )

    assert response.status_code == 302
    record = Attendance.query.filter_by(child_id=child.id).one()
    assert record.status == AttendanceStatus.PRESENT
    assert record.centre_id == centre.id
    assert record.recorded_by is not None


def test_duplicate_attendance_rejected(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")
    client.post(f"/children/{child.id}/attendance/new", data=attendance_form())

    response = client.post(
        f"/children/{child.id}/attendance/new", data=attendance_form()
    )

    assert response.status_code == 400
    assert b"already exists" in response.data
    assert Attendance.query.filter_by(child_id=child.id).count() == 1


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"attendance_date": ""}, b"Attendance date is required"),
        ({"status": ""}, b"Attendance status is required"),
        (
            {"attendance_date": (date.today() + timedelta(days=1)).isoformat()},
            b"cannot be in the future",
        ),
    ],
)
def test_attendance_validation(
    client, db, centre, make_user, make_child, override, expected
):
    child = make_child(centre)
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.post(
        f"/children/{child.id}/attendance/new", data=attendance_form(**override)
    )

    assert response.status_code == 400
    assert expected in response.data
    assert Attendance.query.count() == 0


def test_attendance_before_dob_rejected(client, db, centre, make_user, make_child):
    child = make_child(centre, dob=date.today() - timedelta(days=365))
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.post(
        f"/children/{child.id}/attendance/new",
        data=attendance_form(
            attendance_date=(date.today() - timedelta(days=500)).isoformat()
        ),
    )

    assert response.status_code == 400
    assert b"before the child" in response.data
    assert Attendance.query.count() == 0


# ---------------------------------------------------------------------------
# Editing
# ---------------------------------------------------------------------------
def test_aww_can_edit_attendance(client, db, centre, make_user, make_child, make_attendance):
    child = make_child(centre)
    record = make_attendance(child, status=AttendanceStatus.PRESENT)
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.post(
        f"/children/{child.id}/attendance/{record.id}/edit",
        data=attendance_form(status="ABSENT", note="Fever at home."),
    )

    assert response.status_code == 302
    updated = db.session.get(Attendance, record.id)
    assert updated.status == AttendanceStatus.ABSENT
    assert updated.note == "Fever at home."


def test_edit_to_conflicting_date_rejected(
    client, db, centre, make_user, make_child, make_attendance
):
    child = make_child(centre)
    first = make_attendance(child, date.today(), AttendanceStatus.PRESENT)
    make_attendance(child, date.today() - timedelta(days=1), AttendanceStatus.PRESENT)
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.post(
        f"/children/{child.id}/attendance/{first.id}/edit",
        data=attendance_form(
            attendance_date=(date.today() - timedelta(days=1)).isoformat()
        ),
    )

    assert response.status_code == 400
    assert b"already exists for this date" in response.data


# ---------------------------------------------------------------------------
# Daily register / bulk marking
# ---------------------------------------------------------------------------
def test_daily_register_lists_children(client, db, centre, make_user, make_child):
    make_child(centre, name="Register Child One")
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.get("/attendance/")

    assert response.status_code == 200
    assert b"Daily attendance" in response.data
    assert b"Register Child One" in response.data


def test_bulk_daily_mark_creates_then_updates(
    client, db, centre, make_user, make_child
):
    child_one = make_child(centre, name="Bulk Child One")
    child_two = make_child(centre, name="Bulk Child Two")
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.post(
        "/attendance/daily", data=daily_form(centre, [child_one, child_two])
    )

    assert response.status_code == 302
    assert Attendance.query.count() == 2
    first = Attendance.query.filter_by(child_id=child_one.id).one()
    assert first.status == AttendanceStatus.PRESENT

    # Re-submitting the same day updates instead of duplicating.
    response = client.post(
        "/attendance/daily",
        data=daily_form(
            centre,
            [child_one, child_two],
            **{f"status_{child_one.id}": "ABSENT"},
        ),
    )

    assert response.status_code == 302
    assert Attendance.query.count() == 2
    first = Attendance.query.filter_by(child_id=child_one.id).one()
    assert first.status == AttendanceStatus.ABSENT


def test_bulk_daily_mark_skips_blank_and_invalid(
    client, db, centre, make_user, make_child
):
    child = make_child(centre)
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.post(
        "/attendance/daily",
        data={
            "centre_id": str(centre.id),
            "attendance_date": date.today().isoformat(),
            f"status_{child.id}": "MAYBE",
        },
    )

    assert response.status_code == 302
    assert Attendance.query.count() == 0


# ---------------------------------------------------------------------------
# History / frequent absences / child page
# ---------------------------------------------------------------------------
def test_history_page_filters_by_status(client, db, centre, make_user, make_child, make_attendance):
    child = make_child(centre, name="History Child")
    make_attendance(child, status=AttendanceStatus.ABSENT)
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.get("/attendance/history?status=ABSENT")

    assert response.status_code == 200
    assert b"Attendance history" in response.data
    assert b"History Child" in response.data


def test_frequent_absences_lists_absentees(client, db, centre, make_user, make_child, make_attendance):
    absentee = make_child(centre, name="Absent Child")
    perfect = make_child(centre, name="Perfect Child")
    for day in range(4):
        status = AttendanceStatus.ABSENT if day < 3 else AttendanceStatus.PRESENT
        make_attendance(absentee, date.today() - timedelta(days=day), status)
    make_attendance(perfect, date.today(), AttendanceStatus.PRESENT)
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.get("/attendance/frequent-absences")

    assert response.status_code == 200
    assert b"Frequent absences" in response.data
    assert b"Absent Child" in response.data
    assert b"Perfect Child" not in response.data


def test_child_attendance_history_page(client, db, centre, make_user, make_child, make_attendance):
    child = make_child(centre, name="Profile Child")
    make_attendance(child, status=AttendanceStatus.PRESENT)
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.get(f"/children/{child.id}/attendance")

    assert response.status_code == 200
    assert b"Profile Child" in response.data
    assert b"Monthly summary" in response.data


# ---------------------------------------------------------------------------
# Permissions / centre scoping
# ---------------------------------------------------------------------------
def test_attendance_requires_login(client, db):
    response = client.get("/attendance/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize("role", [UserRole.SUPERVISOR, UserRole.OFFICER])
def test_read_only_roles_cannot_write(client, db, centre, make_user, make_child, role):
    child = make_child(centre)
    make_user("reader", role=role)
    login(client, "reader")

    assert client.get("/attendance/").status_code == 200
    assert client.get(f"/children/{child.id}/attendance").status_code == 200
    assert (
        client.post(f"/children/{child.id}/attendance/new", data=attendance_form()).status_code
        == 403
    )
    assert client.post("/attendance/daily", data=daily_form(centre, [child])).status_code == 403


def test_aww_cannot_view_other_centre_child(
    client, db, centre, other_centre, make_user, make_child
):
    other = make_child(other_centre, name="Other Centre Child")
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    assert client.get(f"/children/{other.id}/attendance").status_code == 403


def test_aww_register_is_centre_scoped(
    client, db, centre, other_centre, make_user, make_child
):
    make_child(centre, name="Own Centre Child")
    make_child(other_centre, name="Other Centre Child")
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.get("/attendance/")

    assert response.status_code == 200
    assert b"Own Centre Child" in response.data
    assert b"Other Centre Child" not in response.data


def test_aww_cannot_view_other_centre_record_via_history(
    client, db, centre, other_centre, make_user, make_child, make_attendance
):
    other = make_child(other_centre, name="Other History Child")
    make_attendance(other, status=AttendanceStatus.ABSENT)
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.get("/attendance/history")

    assert response.status_code == 200
    assert b"Other History Child" not in response.data


# ---------------------------------------------------------------------------
# Beneficiary profile integration
# ---------------------------------------------------------------------------
def test_beneficiary_profile_links_to_attendance(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_att", role=UserRole.AWW, centre=centre)
    login(client, "aww_att")

    response = client.get(f"/beneficiaries/{child.beneficiary_id}")

    assert response.status_code == 200
    assert b"View attendance history" in response.data
    assert f"/children/{child.id}/attendance".encode() in response.data
