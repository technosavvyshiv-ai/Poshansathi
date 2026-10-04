"""Server-side validation helpers (Phase 3 — Beneficiary Management).

Every ``validate_*`` function is pure: it takes a ``request.form``-like mapping
and returns a ``(cleaned, errors)`` tuple.

* ``cleaned`` maps database column names to the parsed/coerced Python values
  that are safe to assign to a model.
* ``errors`` maps field names to a short, user-facing message.

Keeping validation here (instead of in the routes or templates) means the same
rules protect the create route, the update route and any future import path.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.utils.constants import (
    AttendanceStatus,
    BeneficiaryType,
    Gender,
    RiskLevel,
    VaccinationStatus,
)

#: Blood groups accepted for child/mother profiles (demo data only).
BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-")

#: Anganwadi children are pre-school age; the demo accepts up to this age.
MAX_CHILD_AGE_YEARS = 6


class ValidationError(Exception):
    """Raised by the service layer when submitted data fails validation."""

    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__("Validation failed: " + ", ".join(sorted(errors)))


# ---------------------------------------------------------------------------
# Primitive parsers
# ---------------------------------------------------------------------------
def _get(form, key: str) -> str:
    """Return a stripped string value from a form mapping."""
    value = form.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _parse_str(form, key, errors, *, required=False, max_len=None, label=None):
    value = _get(form, key)
    label = label or key.replace("_", " ").capitalize()
    if not value:
        if required:
            errors[key] = f"{label} is required."
        return None
    if max_len and len(value) > max_len:
        errors[key] = f"{label} must be at most {max_len} characters."
        return None
    return value


def _parse_date(form, key, errors, *, required=False, not_future=False, label=None):
    value = _get(form, key)
    label = label or key.replace("_", " ").capitalize()
    if not value:
        if required:
            errors[key] = f"{label} is required."
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        errors[key] = f"{label} must be a valid date."
        return None
    if not_future and parsed > date.today():
        errors[key] = f"{label} cannot be in the future."
        return None
    return parsed


def _parse_decimal(form, key, errors, *, minimum=None, maximum=None, label=None):
    value = _get(form, key)
    label = label or key.replace("_", " ").capitalize()
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        errors[key] = f"{label} must be a number."
        return None
    if minimum is not None and parsed < minimum:
        errors[key] = f"{label} must be at least {minimum}."
        return None
    if maximum is not None and parsed > maximum:
        errors[key] = f"{label} must be at most {maximum}."
        return None
    return parsed


def _parse_int(form, key, errors, *, minimum=None, maximum=None, label=None):
    value = _get(form, key)
    label = label or key.replace("_", " ").capitalize()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        errors[key] = f"{label} must be a whole number."
        return None
    if minimum is not None and parsed < minimum:
        errors[key] = f"{label} must be at least {minimum}."
        return None
    if maximum is not None and parsed > maximum:
        errors[key] = f"{label} must be at most {maximum}."
        return None
    return parsed


def _parse_enum(form, key, enum_cls, errors, *, required=False, default=None, label=None):
    value = _get(form, key)
    label = label or key.replace("_", " ").capitalize()
    if not value:
        if required:
            errors[key] = f"{label} is required."
            return None
        return default
    try:
        return enum_cls(value)
    except ValueError:
        errors[key] = f"{label} is not valid."
        return None


def _parse_phone(form, key, errors, *, label=None):
    value = _get(form, key)
    label = label or key.replace("_", " ").capitalize()
    if not value:
        return None
    digits = value.replace(" ", "").replace("-", "")
    if not digits.isdigit() or len(digits) != 10 or digits[0] not in "6789":
        errors[key] = f"{label} must be a 10-digit mobile number."
        return None
    return digits


def _parse_pincode(form, key, errors, *, label=None):
    value = _get(form, key)
    label = label or key.replace("_", " ").capitalize()
    if not value:
        return None
    if not value.isdigit() or len(value) != 6:
        errors[key] = f"{label} must be a 6-digit PIN code."
        return None
    return value


def _parse_blood_group(form, key, errors, *, label=None):
    value = _get(form, key)
    label = label or key.replace("_", " ").capitalize()
    if not value:
        return None
    if value not in BLOOD_GROUPS:
        errors[key] = f"{label} is not a recognised blood group."
        return None
    return value


def _years_ago(today: date, years: int) -> date:
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # 29 February
        return today.replace(month=2, day=28, year=today.year - years)


def _age_in_years(dob: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# ---------------------------------------------------------------------------
# Beneficiary (common) + type-specific validation
# ---------------------------------------------------------------------------
def validate_beneficiary_fields(form, beneficiary_type: BeneficiaryType):
    """Validate the columns shared by every beneficiary type."""
    errors: dict[str, str] = {}
    is_child = beneficiary_type == BeneficiaryType.CHILD

    cleaned = {
        "full_name": _parse_str(
            form, "full_name", errors, required=True, max_len=150, label="Full name"
        ),
        "date_of_birth": _parse_date(
            form,
            "date_of_birth",
            errors,
            required=is_child,
            not_future=True,
            label="Date of birth",
        ),
        "gender": _parse_enum(
            form, "gender", Gender, errors, required=is_child
        ),
        "guardian_name": _parse_str(
            form, "guardian_name", errors, max_len=150, label="Guardian name"
        ),
        "contact": _parse_phone(form, "contact", errors, label="Contact number"),
        "address": _parse_str(form, "address", errors, max_len=255),
        "registration_date": _parse_date(
            form,
            "registration_date",
            errors,
            not_future=True,
            label="Registration date",
        ),
    }

    # Mothers are always recorded as female, regardless of a submitted value.
    if not is_child:
        cleaned["gender"] = Gender.FEMALE

    if is_child:
        dob = cleaned.get("date_of_birth")
        if dob is not None:
            if dob < _years_ago(date.today(), MAX_CHILD_AGE_YEARS):
                errors["date_of_birth"] = (
                    f"Child must be under {MAX_CHILD_AGE_YEARS} years old."
                )
            elif dob > date.today():
                errors["date_of_birth"] = "Date of birth cannot be in the future."
    else:
        dob = cleaned.get("date_of_birth")
        if dob is not None:
            age = _age_in_years(dob)
            if age < 12 or age > 60:
                errors["date_of_birth"] = (
                    "Age derived from date of birth must be between 12 and 60."
                )

    if not cleaned.get("registration_date"):
        cleaned["registration_date"] = date.today()

    return cleaned, errors


def validate_child_fields(form):
    """Validate the child-specific profile fields."""
    errors: dict[str, str] = {}
    mother_id_raw = _get(form, "mother_id")
    mother_id = None
    if mother_id_raw:
        try:
            mother_id = int(mother_id_raw)
        except ValueError:
            errors["mother_id"] = "Selected mother is not valid."

    cleaned = {
        "birth_weight_kg": _parse_decimal(
            form, "birth_weight_kg", errors, minimum=Decimal("0.5"),
            maximum=Decimal("8.0"), label="Birth weight (kg)",
        ),
        "birth_height_cm": _parse_decimal(
            form, "birth_height_cm", errors, minimum=Decimal("25"),
            maximum=Decimal("70"), label="Birth height (cm)",
        ),
        "blood_group": _parse_blood_group(form, "blood_group", errors),
        "mother_id": mother_id,
    }
    return cleaned, errors


def validate_mother_fields(form, beneficiary_type: BeneficiaryType):
    """Validate the pregnancy/lactation profile fields."""
    errors: dict[str, str] = {}
    cleaned = {
        "age": _parse_int(form, "age", errors, minimum=12, maximum=60),
        "husband_name": _parse_str(
            form, "husband_name", errors, max_len=150, label="Husband name"
        ),
        "pregnancy_number": _parse_int(
            form, "pregnancy_number", errors, minimum=1, maximum=10,
            label="Pregnancy number",
        ),
        "last_menstrual_period": _parse_date(
            form, "last_menstrual_period", errors, not_future=True,
            label="Last menstrual period",
        ),
        "expected_delivery_date": _parse_date(
            form, "expected_delivery_date", errors, label="Expected delivery date"
        ),
        "delivery_date": _parse_date(
            form, "delivery_date", errors, not_future=True, label="Delivery date"
        ),
        "blood_group": _parse_blood_group(form, "blood_group", errors),
        "height_cm": _parse_decimal(
            form, "height_cm", errors, minimum=Decimal("100"),
            maximum=Decimal("200"), label="Height (cm)",
        ),
        "current_risk_level": _parse_enum(
            form, "current_risk_level", RiskLevel, errors, default=RiskLevel.LOW
        ),
    }

    lmp = cleaned.get("last_menstrual_period")
    edd = cleaned.get("expected_delivery_date")
    if lmp and edd and edd <= lmp:
        errors["expected_delivery_date"] = (
            "Expected delivery date must be after the last menstrual period."
        )

    # Derive age from the beneficiary date of birth when the field is blank.
    dob = _parse_date(form, "date_of_birth", errors, not_future=True,
                      label="Date of birth")
    if cleaned.get("age") is None and dob is not None:
        cleaned["age"] = _age_in_years(dob)

    if beneficiary_type == BeneficiaryType.PREGNANT_WOMAN and cleaned.get("delivery_date"):
        errors["delivery_date"] = (
            "A pregnant woman record should not have a delivery date yet."
        )

    return cleaned, errors


# ---------------------------------------------------------------------------
# Centre validation
# ---------------------------------------------------------------------------
def validate_centre_fields(form):
    """Validate an Anganwadi centre form."""
    errors: dict[str, str] = {}
    cleaned = {
        "name": _parse_str(form, "name", errors, required=True, max_len=150, label="Centre name"),
        "code": _parse_str(form, "code", errors, required=True, max_len=50, label="Centre code"),
        "address": _parse_str(form, "address", errors, max_len=255),
        "village": _parse_str(form, "village", errors, max_len=120),
        "district": _parse_str(form, "district", errors, max_len=120),
        "state": _parse_str(form, "state", errors, max_len=120),
        "pincode": _parse_pincode(form, "pincode", errors, label="PIN code"),
        "phone": _parse_phone(form, "phone", errors, label="Phone number"),
        "is_active": _get(form, "is_active") not in ("", "0", "false", "off", "False"),
    }
    return cleaned, errors


# ---------------------------------------------------------------------------
# Growth record validation (Phase 4)
# ---------------------------------------------------------------------------
def validate_growth_fields(form, child):
    """Validate a growth measurement for ``child``.

    Bounds are broad data-integrity guards, **not** clinical thresholds.  The
    growth *status* is decided separately by the documented demo rules in
    :mod:`app.utils.growth_rules`.
    """
    errors: dict[str, str] = {}
    date_of_birth = child.beneficiary.date_of_birth if child.beneficiary else None

    cleaned = {
        "measurement_date": _parse_date(
            form,
            "measurement_date",
            errors,
            required=True,
            not_future=True,
            label="Measurement date",
        ),
        "weight_kg": _parse_decimal(
            form,
            "weight_kg",
            errors,
            minimum=Decimal("0.5"),
            maximum=Decimal("100"),
            label="Weight (kg)",
        ),
        "height_cm": _parse_decimal(
            form,
            "height_cm",
            errors,
            minimum=Decimal("20"),
            maximum=Decimal("200"),
            label="Height (cm)",
        ),
        "muac_cm": _parse_decimal(
            form,
            "muac_cm",
            errors,
            minimum=Decimal("5"),
            maximum=Decimal("40"),
            label="MUAC (cm)",
        ),
        "notes": _parse_str(form, "notes", errors, max_len=1000, label="Notes"),
    }

    if cleaned.get("weight_kg") is None and "weight_kg" not in errors:
        errors["weight_kg"] = "Weight (kg) is required."

    measurement_date = cleaned.get("measurement_date")
    if measurement_date and date_of_birth and measurement_date < date_of_birth:
        errors["measurement_date"] = (
            "Measurement date cannot be before the child's date of birth."
        )

    return cleaned, errors


# ---------------------------------------------------------------------------
# Vaccination record validation (Phase 5)
# ---------------------------------------------------------------------------
def validate_vaccination_fields(form, child):
    """Validate a vaccination record for ``child``.

    The stored ``Vaccination.status`` enum is the source of truth; the rules
    below only keep the submitted data internally consistent.  No clinical
    immunisation schedule is assumed.

    Consistency rules (project-defined, deterministic):

    * ``vaccine_name`` and ``dose_number`` (>= 1) are always required;
    * ``status`` is required and must be one of the stored enum values;
    * an administered date is **required** when the status is ``COMPLETED`` and
      must be blank for every other status;
    * an administered date may not be in the future;
    * both dates (when supplied) must fall on or after the child's date of birth;
    * an administered date may not be before the stored scheduled date.
    """
    errors: dict[str, str] = {}
    date_of_birth = child.beneficiary.date_of_birth if child.beneficiary else None

    cleaned = {
        "vaccine_name": _parse_str(
            form, "vaccine_name", errors, required=True, max_len=120,
            label="Vaccine name",
        ),
        "dose_number": _parse_int(
            form, "dose_number", errors, minimum=1, maximum=20,
            label="Dose number",
        ),
        "scheduled_date": _parse_date(
            form, "scheduled_date", errors, label="Scheduled date"
        ),
        "administered_date": _parse_date(
            form, "administered_date", errors, not_future=True,
            label="Administered date",
        ),
        "status": _parse_enum(
            form, "status", VaccinationStatus, errors, required=True,
            default=VaccinationStatus.UPCOMING,
        ),
        "notes": _parse_str(form, "notes", errors, max_len=1000, label="Notes"),
    }

    if cleaned.get("dose_number") is None and "dose_number" not in errors:
        errors["dose_number"] = "Dose number is required."

    status = cleaned.get("status")
    administered = cleaned.get("administered_date")
    scheduled = cleaned.get("scheduled_date")

    if status == VaccinationStatus.COMPLETED:
        if administered is None and "administered_date" not in errors:
            errors["administered_date"] = (
                "Administered date is required when the status is Completed."
            )
    elif administered is not None:
        errors["administered_date"] = (
            "Clear the administered date or set the status to Completed."
        )

    if administered and date_of_birth and administered < date_of_birth:
        errors["administered_date"] = (
            "Administered date cannot be before the child's date of birth."
        )

    if scheduled and date_of_birth and scheduled < date_of_birth:
        errors["scheduled_date"] = (
            "Scheduled date cannot be before the child's date of birth."
        )

    if administered and scheduled and administered < scheduled:
        errors["administered_date"] = (
            "Administered date cannot be before the scheduled date."
        )

    return cleaned, errors


# ---------------------------------------------------------------------------
# Maternal health (ANC) record validation (Phase 6)
# ---------------------------------------------------------------------------
def validate_maternal_health_fields(form, mother):
    """Validate an antenatal-care record for ``mother``.

    Bounds are broad data-integrity guards, **not** clinical thresholds.  The
    stored ``risk_category`` is chosen by the user; PoshanSathi never derives a
    clinical risk.  Consistency rules (project-defined, deterministic):

    * ``visit_date`` is required, must be a valid date and cannot be in the
      future;
    * the visit date cannot precede the mother's date of birth or the stored
      last menstrual period;
    * ``pregnancy_month`` (1-9), blood pressure and the other measurements use
      broad sanity ranges;
    * diastolic blood pressure must be lower than systolic when both are given;
    * ``risk_category`` is required and must be one of the stored enum values;
    * a next follow-up date cannot be before the ANC visit date.
    """
    errors: dict[str, str] = {}
    beneficiary = mother.beneficiary if mother else None
    date_of_birth = beneficiary.date_of_birth if beneficiary else None
    lmp = mother.last_menstrual_period if mother else None

    cleaned = {
        "visit_date": _parse_date(
            form, "visit_date", errors, required=True, not_future=True,
            label="ANC visit date",
        ),
        "pregnancy_month": _parse_int(
            form, "pregnancy_month", errors, minimum=1, maximum=9,
            label="Pregnancy month",
        ),
        "weight_kg": _parse_decimal(
            form, "weight_kg", errors, minimum=Decimal("20"),
            maximum=Decimal("200"), label="Weight (kg)",
        ),
        "haemoglobin": _parse_decimal(
            form, "haemoglobin", errors, minimum=Decimal("3"),
            maximum=Decimal("20"), label="Haemoglobin (g/dL)",
        ),
        "systolic_bp": _parse_int(
            form, "systolic_bp", errors, minimum=50, maximum=250,
            label="Systolic blood pressure",
        ),
        "diastolic_bp": _parse_int(
            form, "diastolic_bp", errors, minimum=30, maximum=150,
            label="Diastolic blood pressure",
        ),
        "risk_category": _parse_enum(
            form, "risk_category", RiskLevel, errors, required=True,
            default=RiskLevel.LOW,
        ),
        "next_follow_up_date": _parse_date(
            form, "next_follow_up_date", errors, label="Next follow-up date"
        ),
        "notes": _parse_str(form, "notes", errors, max_len=1000, label="Notes"),
    }

    visit_date = cleaned.get("visit_date")
    follow_up = cleaned.get("next_follow_up_date")

    if visit_date and date_of_birth and visit_date < date_of_birth:
        errors["visit_date"] = (
            "ANC visit date cannot be before the mother's date of birth."
        )

    if visit_date and lmp and visit_date < lmp:
        errors["visit_date"] = (
            "ANC visit date cannot be before the last menstrual period."
        )

    if follow_up and visit_date and follow_up < visit_date:
        errors["next_follow_up_date"] = (
            "Next follow-up date cannot be before the ANC visit date."
        )

    systolic = cleaned.get("systolic_bp")
    diastolic = cleaned.get("diastolic_bp")
    if systolic is not None and diastolic is not None and diastolic >= systolic:
        errors["diastolic_bp"] = (
            "Diastolic blood pressure must be lower than systolic blood pressure."
        )

    return cleaned, errors


# ---------------------------------------------------------------------------
# Nutrition / inventory validation (Phase 7)
# ---------------------------------------------------------------------------
def validate_nutrition_item_fields(form):
    """Validate a nutrition item catalogue entry."""
    errors: dict[str, str] = {}
    cleaned = {
        "name": _parse_str(
            form, "name", errors, required=True, max_len=150, label="Item name"
        ),
        "category": _parse_str(
            form, "category", errors, max_len=80, label="Category"
        ),
        "unit": _parse_str(
            form, "unit", errors, required=True, max_len=30, label="Unit"
        ),
        "description": _parse_str(
            form, "description", errors, max_len=1000, label="Description"
        ),
        "is_active": _get(form, "is_active") not in ("", "0", "false", "off", "False"),
    }
    return cleaned, errors


def validate_stock_received_fields(form):
    """Validate a stock-received entry for one inventory row.

    Quantities are broad data-integrity guards, not clinical/ration advice.
    """
    errors: dict[str, str] = {}
    cleaned = {
        "quantity": _parse_decimal(
            form, "quantity", errors, minimum=Decimal("0.01"),
            maximum=Decimal("1000000"), label="Received quantity",
        ),
        "received_date": _parse_date(
            form, "received_date", errors, not_future=True, label="Received date"
        ),
        "expiry_date": _parse_date(
            form, "expiry_date", errors, label="Expiry date"
        ),
        "minimum_stock": _parse_decimal(
            form, "minimum_stock", errors, minimum=Decimal("0"),
            maximum=Decimal("1000000"), label="Minimum stock",
        ),
        "unit": _parse_str(form, "unit", errors, max_len=30, label="Unit"),
    }

    if cleaned.get("quantity") is None and "quantity" not in errors:
        errors["quantity"] = "Received quantity is required."

    received = cleaned.get("received_date")
    expiry = cleaned.get("expiry_date")
    if received and expiry and expiry < received:
        errors["expiry_date"] = (
            "Expiry date cannot be before the received date."
        )

    return cleaned, errors


def validate_nutrition_distribution_fields(form):
    """Validate a nutrition distribution entry.

    Stock availability (quantity cannot exceed current stock) is enforced by
    :mod:`app.services.nutrition_service`, which has access to the inventory
    row.
    """
    errors: dict[str, str] = {}
    cleaned = {
        "item_id": _parse_int(
            form, "item_id", errors, minimum=1, label="Nutrition item"
        ),
        "quantity": _parse_decimal(
            form, "quantity", errors, minimum=Decimal("0.01"),
            maximum=Decimal("1000000"), label="Quantity",
        ),
        "distribution_date": _parse_date(
            form, "distribution_date", errors, required=True, not_future=True,
            label="Distribution date",
        ),
        "notes": _parse_str(form, "notes", errors, max_len=1000, label="Notes"),
    }

    if cleaned.get("item_id") is None and "item_id" not in errors:
        errors["item_id"] = "Please select a nutrition item."

    if cleaned.get("quantity") is None and "quantity" not in errors:
        errors["quantity"] = "Quantity is required."

    return cleaned, errors


# ---------------------------------------------------------------------------
# Attendance validation (Phase 8)
# ---------------------------------------------------------------------------
def validate_attendance_fields(form, child):
    """Validate a daily attendance record for ``child``.

    Rules (project-defined, deterministic):

    * ``attendance_date`` is required, a valid date and cannot be in the future;
    * ``attendance_date`` cannot precede the child's date of birth;
    * ``status`` is required and must be one of the stored enum values
      (``PRESENT`` / ``ABSENT``);
    * ``note`` is optional and limited to the column length.

    The database (and the service layer) additionally prevents two records for
    the same child and date.
    """
    errors: dict[str, str] = {}
    beneficiary = child.beneficiary if child else None
    date_of_birth = beneficiary.date_of_birth if beneficiary else None

    cleaned = {
        "attendance_date": _parse_date(
            form,
            "attendance_date",
            errors,
            required=True,
            not_future=True,
            label="Attendance date",
        ),
        "status": _parse_enum(
            form,
            "status",
            AttendanceStatus,
            errors,
            required=True,
            label="Attendance status",
        ),
        "note": _parse_str(form, "note", errors, max_len=255, label="Note"),
    }

    attendance_date = cleaned.get("attendance_date")
    if attendance_date and date_of_birth and attendance_date < date_of_birth:
        errors["attendance_date"] = (
            "Attendance date cannot be before the child's date of birth."
        )

    return cleaned, errors


__all__ = [
    "BLOOD_GROUPS",
    "MAX_CHILD_AGE_YEARS",
    "ValidationError",
    "validate_attendance_fields",
    "validate_beneficiary_fields",
    "validate_child_fields",
    "validate_maternal_health_fields",
    "validate_mother_fields",
    "validate_centre_fields",
    "validate_growth_fields",
    "validate_nutrition_distribution_fields",
    "validate_nutrition_item_fields",
    "validate_stock_received_fields",
    "validate_vaccination_fields",
]