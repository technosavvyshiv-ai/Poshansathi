"""Shared enumerations for PoshanSathi.

These Python enums are the single source of truth for the status/type values
stored in the database.  Each member name matches its value so the value stored
by SQLAlchemy is the same regardless of whether the enum name or value is used.

Phase 1 only defines the values required by the database schema.  Business rules
that consume them (alert evaluation, vaccination scheduling, ...) arrive in
later phases.
"""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    """Roles described in PROJECT_PLAN.md section 4."""

    ADMIN = "ADMIN"
    AWW = "AWW"
    SUPERVISOR = "SUPERVISOR"
    OFFICER = "OFFICER"


#: Human-readable labels used by the navigation and dashboards.
ROLE_LABELS = {
    UserRole.ADMIN: "Administrator",
    UserRole.AWW: "Anganwadi Worker",
    UserRole.SUPERVISOR: "Supervisor",
    UserRole.OFFICER: "Programme Officer",
}


class BeneficiaryType(str, enum.Enum):
    """Coarse category of a beneficiary record."""

    CHILD = "CHILD"
    PREGNANT_WOMAN = "PREGNANT_WOMAN"
    LACTATING_MOTHER = "LACTATING_MOTHER"


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class RecordStatus(str, enum.Enum):
    """Generic active/inactive flag used for soft deactivation."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class RiskLevel(str, enum.Enum):
    """Configured / demo risk level (never a medical diagnosis)."""

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class NutritionalStatus(str, enum.Enum):
    """Demo growth classification.  Clearly labelled as a demonstration rule."""

    NORMAL = "NORMAL"
    UNDERWEIGHT = "UNDERWEIGHT"
    SEVERE_UNDERWEIGHT = "SEVERE_UNDERWEIGHT"
    OVERWEIGHT = "OVERWEIGHT"


class VaccinationStatus(str, enum.Enum):
    UPCOMING = "UPCOMING"
    DUE = "DUE"
    COMPLETED = "COMPLETED"
    MISSED = "MISSED"


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


class AlertType(str, enum.Enum):
    GROWTH_FOLLOW_UP = "GROWTH_FOLLOW_UP"
    VACCINATION_FOLLOW_UP = "VACCINATION_FOLLOW_UP"
    MATERNAL_FOLLOW_UP = "MATERNAL_FOLLOW_UP"
    LOW_NUTRITION_STOCK = "LOW_NUTRITION_STOCK"
    ATTENDANCE = "ATTENDANCE"
    HOME_VISIT_PENDING = "HOME_VISIT_PENDING"
    GENERAL = "GENERAL"


class AlertSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class VisitType(str, enum.Enum):
    ROUTINE = "ROUTINE"
    GROWTH = "GROWTH"
    VACCINATION = "VACCINATION"
    MATERNAL = "MATERNAL"
    NUTRITION = "NUTRITION"
    FOLLOW_UP = "FOLLOW_UP"


class VisitStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    MISSED = "MISSED"


class SchemeStatus(str, enum.Enum):
    ELIGIBLE = "ELIGIBLE"
    APPLIED = "APPLIED"
    ENROLLED = "ENROLLED"
    REJECTED = "REJECTED"
