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
