"""SQLAlchemy models for PoshanSathi.

Importing this package registers every model on the shared ``db`` metadata so
that ``db.create_all()`` knows about all tables.  Keep the imports below in sync
with the files in this package.
"""

from __future__ import annotations

from app.models.alert import Alert
from app.models.attendance import Attendance
from app.models.audit_log import AuditLog
from app.models.base import TimestampMixin
from app.models.beneficiary import Beneficiary
from app.models.centre import AnganwadiCentre
from app.models.child import Child
from app.models.growth import GrowthRecord
from app.models.home_visit import HomeVisit
from app.models.intervention import Intervention
from app.models.maternal_health import MaternalHealthRecord
from app.models.mother import Mother
from app.models.notification import Notification
from app.models.nutrition import Inventory, NutritionDistribution, NutritionItem
from app.models.scheme import BeneficiaryScheme, WelfareScheme
from app.models.user import User
from app.models.vaccination import Vaccination

__all__ = [
    "Alert",
    "AnganwadiCentre",
    "Attendance",
    "AuditLog",
    "Beneficiary",
    "BeneficiaryScheme",
    "Child",
    "GrowthRecord",
    "HomeVisit",
    "Intervention",
    "Inventory",
    "MaternalHealthRecord",
    "Mother",
    "Notification",
    "NutritionDistribution",
    "NutritionItem",
    "TimestampMixin",
    "User",
    "Vaccination",
    "WelfareScheme",
]
