"""Phase 1 database tests: schema, models, relationships and seed data."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models import (
    AnganwadiCentre,
    Attendance,
    Beneficiary,
    Child,
    GrowthRecord,
    NutritionItem,
    User,
    Vaccination,
)
from app.utils.constants import (
    AttendanceStatus,
    BeneficiaryType,
    Gender,
    RecordStatus,
    UserRole,
)

EXPECTED_TABLES = {
    "anganwadi_centres",
    "users",
    "beneficiaries",
    "mothers",
    "children",
    "growth_records",
    "vaccinations",
    "maternal_health_records",
    "nutrition_items",
    "inventory",
    "nutrition_distributions",
    "attendance",
    "welfare_schemes",
    "beneficiary_schemes",
    "home_visits",
    "interventions",
    "alerts",
    "notifications",
    "audit_logs",
}


def test_all_tables_created(app, db):
    tables = set(inspect(db.engine).get_table_names())
    assert EXPECTED_TABLES.issubset(tables)


def _make_centre(db, code="T-001"):
    centre = AnganwadiCentre(name=f"Test Centre {code}", code=code)
    db.session.add(centre)
    db.session.flush()
    return centre


def test_user_password_is_hashed(db):
    user = User(
        full_name="Test AWW",
        username="test_aww",
        role=UserRole.AWW,
        password_hash="placeholder",
    )
    user.set_password("secret123")
    db.session.add(user)
    db.session.commit()

    assert user.password_hash != "secret123"
    assert user.check_password("secret123") is True
    assert user.check_password("wrong") is False


def test_beneficiary_child_relationship(db):
    centre = _make_centre(db)
    beneficiary = Beneficiary(
        centre=centre,
        beneficiary_type=BeneficiaryType.CHILD,
        full_name="Demo Child",
        date_of_birth=date.today() - timedelta(days=400),
        gender=Gender.FEMALE,
        status=RecordStatus.ACTIVE,
    )
    child = Child(beneficiary=beneficiary, birth_weight_kg=2.8)
    db.session.add(child)
    db.session.commit()

    assert beneficiary.child.id == child.id
    assert child.beneficiary.full_name == "Demo Child"


def test_attendance_unique_constraint(db):
    centre = _make_centre(db, code="T-002")
    beneficiary = Beneficiary(
        centre=centre,
        beneficiary_type=BeneficiaryType.CHILD,
        full_name="Demo Child 2",
        status=RecordStatus.ACTIVE,
    )
    child = Child(beneficiary=beneficiary)
    db.session.add(child)
    db.session.flush()

    today = date.today()
    db.session.add(
        Attendance(
            child=child,
            centre=centre,
            attendance_date=today,
            status=AttendanceStatus.PRESENT,
        )
    )
    db.session.commit()

    db.session.add(
        Attendance(
            child=child,
            centre=centre,
            attendance_date=today,
            status=AttendanceStatus.ABSENT,
        )
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_cascade_delete_child_removes_growth(db):
    centre = _make_centre(db, code="T-003")
    beneficiary = Beneficiary(
        centre=centre,
        beneficiary_type=BeneficiaryType.CHILD,
        full_name="Demo Child 3",
        status=RecordStatus.ACTIVE,
    )
    child = Child(beneficiary=beneficiary)
    db.session.add(child)
    db.session.flush()
    db.session.add(
        GrowthRecord(
            child=child,
            measurement_date=date.today(),
            weight_kg=8.5,
        )
    )
    db.session.commit()

    db.session.delete(beneficiary)
    db.session.commit()

    assert db.session.query(GrowthRecord).count() == 0


def test_seed_database_populates_foundation(app, db):
    from database.seed import seed_database

    result = seed_database()
    assert result.skipped is False

    assert db.session.query(AnganwadiCentre).count() == 5
    assert db.session.query(User).count() == 14
    assert db.session.query(Beneficiary).count() == 140
    assert (
        db.session.query(GrowthRecord).count()
        == 20 * 3 * 5
    )
    assert db.session.query(NutritionItem).count() == len(
        {
            "Take Home Ration (THR)",
            "Ready to Eat (RTE)",
            "Fortified Atta",
            "Chana Dal",
            "Groundnut Chikki",
            "Iron & Folic Acid Tablets",
        }
    )

    # Re-running without force must not duplicate data.
    second = seed_database()
    assert second.skipped is True
    assert db.session.query(AnganwadiCentre).count() == 5


# ---------------------------------------------------------------------------
# Phase 13: constraints / referential integrity regression tests
# ---------------------------------------------------------------------------
def _centre_with_child(db, code, full_name="Constraint Child"):
    centre = AnganwadiCentre(name=f"Test Centre {code}", code=code)
    db.session.add(centre)
    db.session.flush()
    beneficiary = Beneficiary(
        centre=centre,
        beneficiary_type=BeneficiaryType.CHILD,
        full_name=full_name,
        status=RecordStatus.ACTIVE,
    )
    child = Child(beneficiary=beneficiary)
    db.session.add(child)
    db.session.flush()
    return centre, beneficiary, child


def test_vaccination_unique_child_vaccine_dose(db):
    _centre, _ben, child = _centre_with_child(db, "C-010")
    db.session.add(
        Vaccination(
            child=child, vaccine_name="BCG", dose_number=1,
            status="UPCOMING",
        )
    )
    db.session.commit()

    db.session.add(
        Vaccination(
            child=child, vaccine_name="BCG", dose_number=1,
            status="UPCOMING",
        )
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    # A different dose number is allowed.
    db.session.add(
        Vaccination(
            child=child, vaccine_name="BCG", dose_number=2,
            status="UPCOMING",
        )
    )
    db.session.commit()
    assert db.session.query(Vaccination).count() == 2


def test_beneficiary_scheme_unique_constraint(db):
    from app.models import BeneficiaryScheme, WelfareScheme

    _centre, beneficiary, _child = _centre_with_child(db, "C-011")
    scheme = WelfareScheme(name="Constraint Scheme", is_active=True)
    db.session.add(scheme)
    db.session.flush()

    db.session.add(
        BeneficiaryScheme(
            beneficiary_id=beneficiary.id, scheme_id=scheme.id
        )
    )
    db.session.commit()

    db.session.add(
        BeneficiaryScheme(
            beneficiary_id=beneficiary.id, scheme_id=scheme.id
        )
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_cascade_delete_beneficiary_removes_visits_interventions_alerts(db):
    from app.models import (
        Alert,
        HomeVisit,
        Intervention,
        Vaccination,
    )
    from app.utils.constants import AlertSeverity, AlertType, VisitStatus, VisitType

    _centre, beneficiary, _child = _centre_with_child(db, "C-012")
    visit = HomeVisit(
        beneficiary_id=beneficiary.id,
        centre_id=beneficiary.centre_id,
        visit_type=VisitType.ROUTINE,
        scheduled_date=date.today(),
        status=VisitStatus.SCHEDULED,
    )
    db.session.add(visit)
    db.session.flush()
    db.session.add_all(
        [
            Intervention(
                home_visit_id=visit.id,
                beneficiary_id=beneficiary.id,
                intervention_type="Counselling",
                intervention_date=date.today(),
            ),
            Alert(
                beneficiary_id=beneficiary.id,
                alert_type=AlertType.GROWTH_FOLLOW_UP,
                severity=AlertSeverity.MEDIUM,
                message="Delete cascade check.",
            ),
            Vaccination(
                child=beneficiary.child, vaccine_name="BCG", dose_number=1,
                status="UPCOMING",
            ),
        ]
    )
    db.session.commit()

    db.session.delete(beneficiary)
    db.session.commit()

    assert db.session.query(HomeVisit).count() == 0
    assert db.session.query(Intervention).count() == 0
    assert db.session.query(Alert).count() == 0
    assert db.session.query(Vaccination).count() == 0


def test_deleting_child_cascades_attendance(db):
    _centre, beneficiary, _child = _centre_with_child(db, "C-013")
    db.session.add(
        Attendance(
            child_id=beneficiary.child.id,
            centre_id=beneficiary.centre_id,
            attendance_date=date.today(),
            status=AttendanceStatus.PRESENT,
        )
    )
    db.session.commit()

    db.session.delete(beneficiary)
    db.session.commit()

    assert db.session.query(Attendance).count() == 0
