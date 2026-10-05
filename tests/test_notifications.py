"""Phase 12 in-app notification tests: creation, listing, read state, auth."""

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
    HomeVisit,
    Inventory,
    MaternalHealthRecord,
    Mother,
    Notification,
    NutritionItem,
    User,
    Vaccination,
)
from app.services import notification_service
from app.utils.constants import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    BeneficiaryType,
    Gender,
    RecordStatus,
    UserRole,
    VaccinationStatus,
    VisitStatus,
    VisitType,
)
from app.utils.notification_rules import NotificationCategory

PASSWORD = "password123"
TODAY = date.today()


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def centre(db):
    centre = AnganwadiCentre(name="Notif Centre A", code="NTA-001", is_active=True)
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
    def make(centre, name="Notif Child"):
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=BeneficiaryType.CHILD,
            full_name=name,
            date_of_birth=TODAY - timedelta(days=730),
            gender=Gender.FEMALE,
            status=RecordStatus.ACTIVE,
            registration_date=TODAY,
        )
        child = Child(beneficiary=beneficiary)
        db.session.add(child)
        db.session.commit()
        return child

    return make


@pytest.fixture()
def make_mother(db):
    def make(centre, name="Notif Mother"):
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=BeneficiaryType.PREGNANT_WOMAN,
            full_name=name,
            date_of_birth=TODAY - timedelta(days=365 * 25),
            gender=Gender.FEMALE,
            status=RecordStatus.ACTIVE,
            registration_date=TODAY,
        )
        mother = Mother(beneficiary=beneficiary)
        db.session.add(mother)
        db.session.commit()
        return mother

    return make


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------
def test_create_and_list_notifications(db, make_user):
    user = make_user("notif_user", role=UserRole.AWW)
    notification_service.create_notification(
        user, title="First", message="One", category=NotificationCategory.GENERAL
    )
    notification_service.create_notification(
        user, title="Second", message="Two", category=NotificationCategory.LOW_STOCK
    )

    all_items = notification_service.list_for_user(user)
    assert len(all_items) == 2
    assert notification_service.unread_count(user) == 2

    low_stock = notification_service.list_for_user(
        user, category=NotificationCategory.LOW_STOCK
    )
    assert len(low_stock) == 1
    assert low_stock[0].title == "Second"

    search = notification_service.list_for_user(user, search="One")
    assert len(search) == 1
    assert search[0].title == "First"


def test_read_state_transitions(db, make_user):
    user = make_user("notif_user", role=UserRole.AWW)
    notification = notification_service.create_notification(
        user, title="Read me", category=NotificationCategory.GENERAL
    )
    assert notification.is_read is False
    assert notification.read_at is None

    notification_service.mark_read(notification)
    assert notification.is_read is True
    assert notification.read_at is not None
    assert notification_service.unread_count(user) == 0

    notification_service.mark_unread(notification)
    assert notification.is_read is False
    assert notification.read_at is None

    notification_service.mark_all_read(user)
    assert notification_service.unread_count(user) == 0
    counts = notification_service.status_counts(user)
    assert counts == {"unread": 0, "read": 1, "total": 1}


def test_notification_list_is_user_scoped(db, make_user):
    first = make_user("notif_first", role=UserRole.AWW)
    second = make_user("notif_second", role=UserRole.AWW)
    notification_service.create_notification(
        first, title="For first", category=NotificationCategory.GENERAL
    )
    notification_service.create_notification(
        second, title="For second", category=NotificationCategory.GENERAL
    )

    first_items = notification_service.list_for_user(first)
    assert [item.title for item in first_items] == ["For first"]


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------
def test_notifications_require_login(client, db):
    response = client.get("/notifications/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_notification_index_lists_own(client, db, make_user):
    user = make_user("notif_aww", role=UserRole.AWW)
    notification_service.create_notification(
        user, title="Visible notification", category=NotificationCategory.ALERT
    )
    login(client, "notif_aww")

    response = client.get("/notifications/")
    assert response.status_code == 200
    assert b"Visible notification" in response.data


def test_notification_read_unread_routes(client, db, make_user):
    user = make_user("notif_aww", role=UserRole.AWW)
    notification = notification_service.create_notification(
        user, title="Toggle me", category=NotificationCategory.GENERAL
    )
    login(client, "notif_aww")

    assert client.post(f"/notifications/{notification.id}/read").status_code == 302
    assert db.session.get(Notification, notification.id).is_read is True

    assert client.post(f"/notifications/{notification.id}/unread").status_code == 302
    assert db.session.get(Notification, notification.id).is_read is False

    assert client.post("/notifications/read-all").status_code == 302
    assert db.session.get(Notification, notification.id).is_read is True


def test_cannot_modify_another_users_notification(client, db, make_user):
    owner = make_user("notif_owner", role=UserRole.AWW)
    make_user("notif_intruder", role=UserRole.AWW)
    notification = notification_service.create_notification(
        owner, title="Owner only", category=NotificationCategory.GENERAL
    )
    login(client, "notif_intruder")

    response = client.post(f"/notifications/{notification.id}/read")
    assert response.status_code == 403
    assert db.session.get(Notification, notification.id).is_read is False


def test_notification_filters(client, db, make_user):
    user = make_user("notif_aww", role=UserRole.AWW)
    first = notification_service.create_notification(
        user, title="Alpha alert", category=NotificationCategory.ALERT
    )
    notification_service.create_notification(
        user, title="Beta stock", category=NotificationCategory.LOW_STOCK
    )
    notification_service.mark_read(first)
    login(client, "notif_aww")

    unread = client.get("/notifications/?status=unread")
    assert unread.status_code == 200
    assert b"Beta stock" in unread.data
    assert b"Alpha alert" not in unread.data

    by_category = client.get(
        "/notifications/?category=" + NotificationCategory.ALERT
    )
    assert b"Alpha alert" in by_category.data
    assert b"Beta stock" not in by_category.data

    by_search = client.get("/notifications/?q=Beta")
    assert b"Beta stock" in by_search.data
    assert b"Alpha alert" not in by_search.data


# ---------------------------------------------------------------------------
# Deterministic generation
# ---------------------------------------------------------------------------
def test_generate_for_user_creates_notifications(
    db, centre, make_user, make_child, make_mother
):
    child = make_child(centre)
    mother = make_mother(centre)
    aww = make_user("notif_aww", role=UserRole.AWW, centre=centre)

    item = NutritionItem(name="Notif Ration", unit="kg", is_active=True)
    db.session.add(item)
    db.session.flush()

    db.session.add_all(
        [
            Vaccination(
                child_id=child.id, vaccine_name="OPV", dose_number=1,
                scheduled_date=TODAY + timedelta(days=1),
                status=VaccinationStatus.UPCOMING,
            ),
            MaternalHealthRecord(
                mother_id=mother.id, visit_date=TODAY - timedelta(days=30),
                next_follow_up_date=TODAY - timedelta(days=1),
                risk_category="LOW",
            ),
            HomeVisit(
                beneficiary_id=child.beneficiary_id, centre_id=centre.id,
                visit_type=VisitType.ROUTINE,
                scheduled_date=TODAY - timedelta(days=1),
                status=VisitStatus.SCHEDULED,
            ),
            Inventory(
                centre_id=centre.id, item_id=item.id,
                opening_stock=Decimal("0"), received_quantity=Decimal("5"),
                distributed_quantity=Decimal("0"), minimum_stock=Decimal("25"),
                unit="kg",
            ),
            Alert(
                beneficiary_id=child.beneficiary_id, child_id=child.id,
                alert_type=AlertType.GROWTH_FOLLOW_UP,
                severity=AlertSeverity.MEDIUM, message="Open alert.",
                status=AlertStatus.OPEN,
            ),
        ]
    )
    db.session.commit()

    result = notification_service.generate_for_user(aww)
    assert result["total"] >= 5

    categories = {
        item.category for item in notification_service.list_for_user(aww)
    }
    assert NotificationCategory.VACCINATION in categories
    assert NotificationCategory.MATERNAL_FOLLOW_UP in categories
    assert NotificationCategory.HOME_VISIT in categories
    assert NotificationCategory.LOW_STOCK in categories
    assert NotificationCategory.ALERT in categories

    # Idempotent: a second run adds nothing.
    before = len(notification_service.list_for_user(aww))
    notification_service.generate_for_user(aww)
    assert len(notification_service.list_for_user(aww)) == before


def test_scan_route_generates_notifications(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("notif_aww", role=UserRole.AWW, centre=centre)
    db.session.add(
        Vaccination(
            child_id=child.id, vaccine_name="Measles", dose_number=1,
            scheduled_date=TODAY, status=VaccinationStatus.DUE,
        )
    )
    db.session.commit()
    login(client, "notif_aww")

    response = client.post("/notifications/scan")
    assert response.status_code == 302

    titles = [item.title for item in Notification.query.all()]
    assert any("Vaccination due" in title for title in titles)


def test_generate_is_centre_scoped_for_aww(
    db, centre, make_user, make_child
):
    other_centre = AnganwadiCentre(name="Notif Centre B", code="NTB-001", is_active=True)
    db.session.add(other_centre)
    db.session.commit()
    other_child = make_child(other_centre, name="Other Centre Notif Child")
    db.session.add(
        Vaccination(
            child=other_child, vaccine_name="BCG", dose_number=1,
            scheduled_date=TODAY, status=VaccinationStatus.DUE,
        )
    )
    db.session.commit()

    aww = make_user("notif_aww", role=UserRole.AWW, centre=centre)
    notification_service.generate_for_user(aww)

    assert notification_service.list_for_user(aww) == []
