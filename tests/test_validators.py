"""Phase 13 validator unit tests.

Pure unit tests for the server-side validation helpers in
:mod:`app.utils.validators` — no database required.  Each module's route tests
already exercise the happy/sad paths end to end; these tests pin down the
individual field rules and edge cases in isolation.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.utils.constants import BeneficiaryType
from app.utils.validators import (
    validate_attendance_fields,
    validate_beneficiary_fields,
    validate_beneficiary_scheme_fields,
    validate_child_fields,
    validate_growth_fields,
    validate_home_visit_fields,
    validate_intervention_fields,
    validate_maternal_health_fields,
    validate_mother_fields,
    validate_nutrition_distribution_fields,
    validate_scheme_fields,
    validate_stock_received_fields,
    validate_vaccination_fields,
    validate_visit_completion_fields,
)

TODAY = date.today()


class _ChildLike:
    """Minimal stand-in for a Child/Mother with a beneficiary."""

    def __init__(self, date_of_birth=None):
        self.beneficiary = type("B", (), {"date_of_birth": date_of_birth})()


class _MotherLike:
    """Stand-in for a Mother with beneficiary + LMP fields."""

    def __init__(self, date_of_birth=None):
        self.beneficiary = type("B", (), {"date_of_birth": date_of_birth})()
        self.last_menstrual_period = None


# ---------------------------------------------------------------------------
# Beneficiary fields
# ---------------------------------------------------------------------------
class TestBeneficiaryFields:
    def test_valid_child(self):
        cleaned, errors = validate_beneficiary_fields(
            {
                "full_name": "Baby Doe",
                "date_of_birth": (TODAY - timedelta(days=400)).isoformat(),
                "gender": "FEMALE",
                "guardian_name": "Guardian",
                "contact": "9876543210",
                "registration_date": TODAY.isoformat(),
            },
            BeneficiaryType.CHILD,
        )
        assert errors == {}
        assert cleaned["full_name"] == "Baby Doe"
        assert cleaned["gender"].value == "FEMALE"

    def test_child_older_than_six_rejected(self):
        _cleaned, errors = validate_beneficiary_fields(
            {"full_name": "Older Kid",
             "date_of_birth": (TODAY - timedelta(days=7 * 365)).isoformat(),
             "gender": "MALE"},
            BeneficiaryType.CHILD,
        )
        assert "under 6" in errors["date_of_birth"]

    def test_child_future_dob_rejected(self):
        _cleaned, errors = validate_beneficiary_fields(
            {"full_name": "Future Kid",
             "date_of_birth": (TODAY + timedelta(days=1)).isoformat(),
             "gender": "MALE"},
            BeneficiaryType.CHILD,
        )
        assert errors["date_of_birth"]

    def test_child_name_required(self):
        _cleaned, errors = validate_beneficiary_fields(
            {"full_name": ""}, BeneficiaryType.CHILD
        )
        assert "Full name is required" in errors["full_name"]

    def test_contact_must_be_10_digit_mobile(self):
        for value in ("12345", "abcdefghij", "0987654321"):
            _cleaned, errors = validate_beneficiary_fields(
                {"contact": value}, BeneficiaryType.CHILD
            )
            assert errors["contact"]
        _cleaned, errors = validate_beneficiary_fields(
            {"contact": "9876543210"}, BeneficiaryType.CHILD
        )
        assert "contact" not in errors

    def test_mother_age_band_enforced(self):
        ten_years_ago = TODAY.replace(year=TODAY.year - 10)
        sixty_two_years_ago = TODAY.replace(year=TODAY.year - 62)
        twenty_five_years_ago = TODAY.replace(year=TODAY.year - 25)
        too_young = validate_beneficiary_fields(
            {"full_name": "X", "date_of_birth": ten_years_ago.isoformat()},
            BeneficiaryType.PREGNANT_WOMAN,
        )[1]
        too_old = validate_beneficiary_fields(
            {"full_name": "X", "date_of_birth": sixty_two_years_ago.isoformat()},
            BeneficiaryType.PREGNANT_WOMAN,
        )[1]
        valid = validate_beneficiary_fields(
            {"full_name": "X", "date_of_birth": twenty_five_years_ago.isoformat()},
            BeneficiaryType.PREGNANT_WOMAN,
        )[1]
        assert "between 12 and 60" in too_young["date_of_birth"]
        assert "between 12 and 60" in too_old["date_of_birth"]
        assert "date_of_birth" not in valid

    def test_mothers_always_recorded_female(self):
        cleaned, _errors = validate_beneficiary_fields(
            {"gender": "MALE"}, BeneficiaryType.LACTATING_MOTHER
        )
        assert cleaned["gender"].value == "FEMALE"


# ---------------------------------------------------------------------------
# Child / mother profile fields
# ---------------------------------------------------------------------------
class TestChildAndMotherFields:
    def test_birth_weight_bounds(self):
        ok, e1 = validate_child_fields({"birth_weight_kg": "3.2"})
        low, e2 = validate_child_fields({"birth_weight_kg": "0.1"})
        high, e3 = validate_child_fields({"birth_weight_kg": "9"})
        assert not e1 and e2 and e3

    def test_mother_delivery_rules(self):
        # Pregnant woman must not have a delivery date.
        _c, e1 = validate_mother_fields(
            {"delivery_date": TODAY.isoformat()}, BeneficiaryType.PREGNANT_WOMAN
        )
        assert e1["delivery_date"]
        # Lactating mother may.
        _c, e2 = validate_mother_fields(
            {"delivery_date": TODAY.isoformat()}, BeneficiaryType.LACTATING_MOTHER
        )
        assert "delivery_date" not in e2

    def test_edd_must_follow_lmp(self):
        _c, errors = validate_mother_fields(
            {
                "last_menstrual_period": TODAY.isoformat(),
                "expected_delivery_date": (TODAY - timedelta(days=1)).isoformat(),
            },
            BeneficiaryType.PREGNANT_WOMAN,
        )
        assert "after the last menstrual period" in errors["expected_delivery_date"]


# ---------------------------------------------------------------------------
# Growth fields
# ---------------------------------------------------------------------------
class TestGrowthFields:
    CHILD = _ChildLike(TODAY - timedelta(days=365))

    def test_weight_required(self):
        _c, errors = validate_growth_fields({"weight_kg": ""}, self.CHILD)
        assert "Weight (kg) is required" in errors["weight_kg"]

    def test_weight_bounds_are_data_guards(self):
        _c, e1 = validate_growth_fields({"weight_kg": "0.1"}, self.CHILD)
        _c, e2 = validate_growth_fields({"weight_kg": "500"}, self.CHILD)
        assert e1 and e2

    def test_measurement_before_birth_rejected(self):
        _c, errors = validate_growth_fields(
            {
                "weight_kg": "8",
                "measurement_date": (TODAY - timedelta(days=400)).isoformat(),
            },
            self.CHILD,
        )
        assert "before the child's date of birth" in errors["measurement_date"]

    def test_future_measurement_rejected(self):
        _c, errors = validate_growth_fields(
            {
                "weight_kg": "8",
                "measurement_date": (TODAY + timedelta(days=1)).isoformat(),
            },
            self.CHILD,
        )
        assert "cannot be in the future" in errors["measurement_date"]


# ---------------------------------------------------------------------------
# Vaccination fields
# ---------------------------------------------------------------------------
class TestVaccinationFields:
    CHILD = _ChildLike(TODAY - timedelta(days=365))

    def _form(self, **overrides):
        data = {
            "vaccine_name": "BCG",
            "dose_number": "1",
            "status": "COMPLETED",
            "administered_date": TODAY.isoformat(),
            "scheduled_date": (TODAY - timedelta(days=10)).isoformat(),
        }
        data.update(overrides)
        return data

    def test_completed_requires_administered_date(self):
        _c, errors = validate_vaccination_fields(
            self._form(administered_date=""), self.CHILD
        )
        assert "Administered date is required" in errors["administered_date"]

    def test_pending_status_must_not_have_administered_date(self):
        _c, errors = validate_vaccination_fields(
            self._form(status="UPCOMING"), self.CHILD
        )
        assert "Clear the administered date" in errors["administered_date"]

    def test_dose_number_required_and_positive(self):
        _c, e1 = validate_vaccination_fields(self._form(dose_number=""), self.CHILD)
        _c, e2 = validate_vaccination_fields(self._form(dose_number="0"), self.CHILD)
        assert e1 and e2

    def test_administered_cannot_precede_scheduled(self):
        _c, errors = validate_vaccination_fields(
            self._form(
                scheduled_date=TODAY.isoformat(),
                administered_date=(TODAY - timedelta(days=1)).isoformat(),
            ),
            self.CHILD,
        )
        assert "before the scheduled date" in errors["administered_date"]


# ---------------------------------------------------------------------------
# Maternal health fields
# ---------------------------------------------------------------------------
class TestMaternalFields:
    MOTHER = _MotherLike(TODAY - timedelta(days=365 * 25))

    def _form(self, **overrides):
        data = {
            "visit_date": TODAY.isoformat(),
            "risk_category": "LOW",
            "systolic_bp": "120",
            "diastolic_bp": "80",
        }
        data.update(overrides)
        return data

    def test_visit_date_required(self):
        _c, errors = validate_maternal_health_fields(
            self._form(visit_date=""), self.MOTHER
        )
        assert "ANC visit date is required" in errors["visit_date"]

    def test_diastolic_must_be_lower_than_systolic(self):
        _c, errors = validate_maternal_health_fields(
            self._form(systolic_bp="110", diastolic_bp="110"), self.MOTHER
        )
        assert "lower than systolic" in errors["diastolic_bp"]

    def test_follow_up_cannot_precede_visit(self):
        _c, errors = validate_maternal_health_fields(
            self._form(next_follow_up_date=(TODAY - timedelta(days=1)).isoformat()),
            self.MOTHER,
        )
        assert "before the ANC visit date" in errors["next_follow_up_date"]


# ---------------------------------------------------------------------------
# Attendance fields
# ---------------------------------------------------------------------------
class TestAttendanceFields:
    CHILD = _ChildLike(TODAY - timedelta(days=365))

    def test_date_and_status_required(self):
        _c, e1 = validate_attendance_fields(
            {"attendance_date": "", "status": "PRESENT"}, self.CHILD
        )
        _c, e2 = validate_attendance_fields(
            {"attendance_date": TODAY.isoformat(), "status": ""}, self.CHILD
        )
        _c, e3 = validate_attendance_fields(
            {"attendance_date": TODAY.isoformat(), "status": "LATE"}, self.CHILD
        )
        assert e1 and e2 and e3

    def test_future_and_before_dob_rejected(self):
        _c, e1 = validate_attendance_fields(
            {"attendance_date": (TODAY + timedelta(days=1)).isoformat(),
             "status": "PRESENT"},
            self.CHILD,
        )
        _c, e2 = validate_attendance_fields(
            {"attendance_date": (TODAY - timedelta(days=400)).isoformat(),
             "status": "PRESENT"},
            self.CHILD,
        )
        assert e1 and e2

    def test_note_max_length(self):
        _c, errors = validate_attendance_fields(
            {"attendance_date": TODAY.isoformat(),
             "status": "PRESENT",
             "note": "x" * 256},
            self.CHILD,
        )
        assert errors["note"]


# ---------------------------------------------------------------------------
# Visit / intervention fields
# ---------------------------------------------------------------------------
class TestVisitFields:
    def test_scheduled_date_and_beneficiary_required(self):
        _c, e1 = validate_home_visit_fields({"scheduled_date": ""})
        _c, e2 = validate_home_visit_fields(
            {"beneficiary_id": "", "scheduled_date": TODAY.isoformat()}
        )
        assert "Scheduled date is required" in e1["scheduled_date"]
        assert "Please select a beneficiary" in e2["beneficiary_id"]

    def test_future_scheduled_date_is_allowed(self):
        cleaned, errors = validate_home_visit_fields(
            {
                "beneficiary_id": "1",
                "visit_type": "ROUTINE",
                "scheduled_date": (TODAY + timedelta(days=7)).isoformat(),
            }
        )
        assert errors == {}
        assert cleaned["scheduled_date"] > TODAY

    def test_completion_date_not_future(self):
        _c, e1 = validate_visit_completion_fields(
            {"completed_date": (TODAY + timedelta(days=1)).isoformat()}
        )
        _c, e2 = validate_visit_completion_fields({"completed_date": ""})
        assert e1 and e2

    def test_follow_up_required_when_flagged(self):
        _c, errors = validate_intervention_fields(
            {
                "intervention_type": "Counselling",
                "intervention_date": TODAY.isoformat(),
                "follow_up_required": "on",
                "follow_up_date": "",
            }
        )
        assert "required when follow-up is requested" in errors["follow_up_date"]

    def test_follow_up_cannot_precede_intervention(self):
        _c, errors = validate_intervention_fields(
            {
                "intervention_type": "Counselling",
                "intervention_date": TODAY.isoformat(),
                "follow_up_required": "on",
                "follow_up_date": (TODAY - timedelta(days=1)).isoformat(),
            }
        )
        assert "before the intervention date" in errors["follow_up_date"]

    def test_follow_up_date_allowed_without_flag(self):
        cleaned, errors = validate_intervention_fields(
            {
                "intervention_type": "Counselling",
                "intervention_date": TODAY.isoformat(),
            }
        )
        assert errors == {}
        assert cleaned["follow_up_required"] is False


# ---------------------------------------------------------------------------
# Nutrition / inventory fields
# ---------------------------------------------------------------------------
class TestNutritionFields:
    def test_distribution_quantity_required_and_positive(self):
        _c, e1 = validate_nutrition_distribution_fields({"quantity": ""})
        _c, e2 = validate_nutrition_distribution_fields({"quantity": "0"})
        assert e1 and e2

    def test_expiry_must_follow_received(self):
        _c, errors = validate_stock_received_fields(
            {
                "quantity": "10",
                "received_date": TODAY.isoformat(),
                "expiry_date": (TODAY - timedelta(days=1)).isoformat(),
            }
        )
        assert "before the received date" in errors["expiry_date"]

    def test_stock_quantity_bounds(self):
        _c, e1 = validate_stock_received_fields({"quantity": "0"})
        _c, e2 = validate_stock_received_fields({"quantity": "2000000"})
        assert e1 and e2


# ---------------------------------------------------------------------------
# Scheme fields
# ---------------------------------------------------------------------------
class TestSchemeFields:
    def test_name_required_and_unique_message_shape(self):
        _c, errors = validate_scheme_fields({"name": ""})
        assert "Scheme name is required" in errors["name"]

    def test_link_status_and_scheme_required(self):
        _c, e1 = validate_beneficiary_scheme_fields({"scheme_id": ""})
        _c, e2 = validate_beneficiary_scheme_fields(
            {"scheme_id": "1", "status": ""}
        )
        _c, e3 = validate_beneficiary_scheme_fields(
            {"scheme_id": "1", "status": "SOMEDAY"}
        )
        assert e1 and e2 and e3

    def test_applied_date_not_future(self):
        _c, errors = validate_beneficiary_scheme_fields(
            {
                "scheme_id": "1",
                "status": "ELIGIBLE",
                "applied_date": (TODAY + timedelta(days=1)).isoformat(),
            }
        )
        assert "cannot be in the future" in errors["applied_date"]

    def test_valid_link(self):
        cleaned, errors = validate_beneficiary_scheme_fields(
            {
                "scheme_id": "3",
                "status": "APPLIED",
                "applied_date": TODAY.isoformat(),
            }
        )
        assert errors == {}
        assert cleaned["scheme_id"] == 3
        assert cleaned["status"].value == "APPLIED"
