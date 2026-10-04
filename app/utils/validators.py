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

from app.utils.constants import BeneficiaryType, Gender, RiskLevel

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


__all__ = [
    "BLOOD_GROUPS",
    "MAX_CHILD_AGE_YEARS",
    "ValidationError",
    "validate_beneficiary_fields",
    "validate_child_fields",
    "validate_mother_fields",
    "validate_centre_fields",
]