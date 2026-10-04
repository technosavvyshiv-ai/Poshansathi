"""Synthetic demo data seeder for PoshanSathi (Phase 1).

Creates clearly fictional centres, users, beneficiaries and the connected
records needed to exercise the schema.  It is safe to re-run: by default it
refuses to seed a non-empty database (use ``force=True`` to wipe and reseed).

Run through the Flask CLI::

    flask --app app.py init-db
    flask --app app.py seed-db

or directly::

    python -m database.seed

All names, contacts and addresses are fictional.  Never use real beneficiary
data.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Allow ``python database/seed.py`` from the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.extensions import db  # noqa: E402
from app.models import (  # noqa: E402
    Alert,
    AnganwadiCentre,
    Attendance,
    AuditLog,
    Beneficiary,
    BeneficiaryScheme,
    Child,
    GrowthRecord,
    HomeVisit,
    Intervention,
    Inventory,
    MaternalHealthRecord,
    Mother,
    Notification,
    NutritionDistribution,
    NutritionItem,
    User,
    Vaccination,
    WelfareScheme,
)
from app.utils.constants import (  # noqa: E402
    AlertSeverity,
    AlertStatus,
    AlertType,
    AttendanceStatus,
    BeneficiaryType,
    Gender,
    NutritionalStatus,
    RecordStatus,
    RiskLevel,
    SchemeStatus,
    UserRole,
    VaccinationStatus,
    VisitStatus,
    VisitType,
)

RANDOM_SEED = 20240101
DEMO_PASSWORD = "password123"

TODAY = date.today()

# ----------------------------------------------------------------------------
# Reference / fictional data
# ----------------------------------------------------------------------------
CENTRES = [
    ("Anganwadi Centre - Rampur", "AWC-001", "Rampur", "Bhopal", "Madhya Pradesh", "462001", "9000000001"),
    ("Anganwadi Centre - Bijli Nagar", "AWC-002", "Bijli Nagar", "Bhopal", "Madhya Pradesh", "462002", "9000000002"),
    ("Anganwadi Centre - Sewa Sadan", "AWC-003", "Sewa Sadan", "Raisen", "Madhya Pradesh", "464551", "9000000003"),
    ("Anganwadi Centre - Kolar", "AWC-004", "Kolar", "Bhopal", "Madhya Pradesh", "462042", "9000000004"),
    ("Anganwadi Centre - Berasia", "AWC-005", "Berasia", "Bhopal", "Madhya Pradesh", "463106", "9000000005"),
]

MALE_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayush",
    "Krishna", "Ishaan", "Rohan", "Karan", "Manish", "Suresh", "Ramesh",
    "Deepak", "Anil", "Rahul", "Vikram", "Naveen",
]
FEMALE_NAMES = [
    "Ananya", "Diya", "Aadhya", "Isha", "Kavya", "Pari", "Anika", "Navya",
    "Saanvi", "Myra", "Priya", "Neha", "Pooja", "Sunita", "Rekha", "Meena",
    "Kavita", "Seema", "Lalita", "Anita",
]
SURNAMES = [
    "Sharma", "Verma", "Patel", "Yadav", "Kushwaha", "Ahirwar", "Malviya",
    "Rathore", "Chouhan", "Tiwari", "Dubey", "Sahu", "Thakur", "Pawar",
    "Meena", "Jaiswal", "Nagar", "Lodhi", "Raikwar", "Vishwakarma",
]

VACCINE_SCHEDULE = [
    ("BCG", 1, 0),
    ("Hepatitis B", 1, 0),
    ("OPV", 1, 42),
    ("Pentavalent", 1, 42),
    ("OPV", 2, 70),
    ("Measles", 1, 270),
]

NUTRITION_ITEMS = [
    ("Take Home Ration (THR)", "Ration", "kg", "Fortified blended food for children and mothers."),
    ("Ready to Eat (RTE)", "Ration", "packet", "Energy-dense ready-to-eat snack."),
    ("Fortified Atta", "Ration", "kg", "Wheat flour fortified with iron and folic acid."),
    ("Chana Dal", "Pulses", "kg", "Protein-rich pulse for supplementary nutrition."),
    ("Groundnut Chikki", "Snack", "packet", "High-energy groundnut and jaggery snack."),
    ("Iron & Folic Acid Tablets", "Supplement", "strip", "IFA supplement for pregnant and lactating mothers."),
]

SCHEMES = [
    ("Integrated Child Development Services (ICDS)", "Child Welfare",
     "Children under 6, pregnant and lactating mothers",
     "Supplementary nutrition, immunisation, health check-ups and pre-school education.",
     "Families with children under 6 or pregnant/lactating mothers.",
     "Age proof, residence proof, Mother and Child Protection card.",
     "Register at the local Anganwadi centre.",
     "Demonstration scheme information only; not an official eligibility determination."),
    ("Pradhan Mantri Matru Vandana Yojana (PMMVY)", "Maternity Benefit",
     "Pregnant and lactating mothers",
     "Cash incentive for the first living child to compensate for wage loss.",
     "Pregnant and lactating mothers (first living child), excluding those covered by similar benefits.",
     "Aadhaar, bank account details, MCP card.",
     "Apply through the PMMVY portal or Anganwadi worker.",
     "Demonstration scheme information only."),
    ("Poshan Abhiyaan", "Nutrition Mission",
     "Children, pregnant women and lactating mothers",
     "Improved nutritional outcomes through convergence and technology.",
     "Focus districts and beneficiaries identified by the programme.",
     "MCP card, Aadhaar.",
     "Through Anganwadi and health functionaries.",
     "Demonstration scheme information only."),
    ("Mid-Day Meal Scheme", "School Nutrition",
     "School-going children",
     "Hot cooked meals in schools to improve attendance and nutrition.",
     "Children studying in government or aided schools.",
     "School enrolment details.",
     "Through the school administration.",
     "Demonstration scheme information only."),
    ("National Health Mission - Immunization", "Health",
     "Infants and children",
     "Free routine immunisation through the universal immunisation programme.",
     "All infants and children per the immunisation schedule.",
     "MCP card.",
     "Visit the nearest health centre on the immunisation day.",
     "Demonstration scheme information only."),
    ("Janani Suraksha Yojana (JSY)", "Maternity Benefit",
     "Pregnant women",
     "Cash assistance to promote institutional delivery.",
     "Pregnant women from eligible categories.",
     "MCP card, Aadhaar, bank details.",
     "Through the health worker / ASHA.",
     "Demonstration scheme information only."),
]

GROWTH_STATUSES = [
    NutritionalStatus.NORMAL,
    NutritionalStatus.NORMAL,
    NutritionalStatus.NORMAL,
    NutritionalStatus.UNDERWEIGHT,
    NutritionalStatus.SEVERE_UNDERWEIGHT,
    NutritionalStatus.OVERWEIGHT,
]


@dataclass
class SeedResult:
    """Outcome of a seeding run."""

    created: dict[str, int] = field(default_factory=dict)
    skipped: bool = False

    def summary(self) -> str:
        if self.skipped:
            return (
                "Seed skipped: the database already contains data. "
                "Use `flask --app app.py reset-db` first to reseed from scratch."
            )
        lines = ["Synthetic demo data inserted:"]
        for name, count in self.created.items():
            lines.append(f"  - {name}: {count}")
        lines.append(f"  Demo password for all accounts: {DEMO_PASSWORD}")
        return "\n".join(lines)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _random_name(gender: Gender) -> str:
    first = random.choice(MALE_NAMES if gender == Gender.MALE else FEMALE_NAMES)
    return f"{first} {random.choice(SURNAMES)}"


def _random_contact() -> str:
    return "9" + "".join(str(random.randint(0, 9)) for _ in range(9))


def _random_address(centre_index: int) -> str:
    house = random.randint(1, 250)
    return f"House {house}, {CENTRES[centre_index][2]}"


def _count(bucket: dict[str, int], key: str, amount: int = 1) -> None:
    bucket[key] = bucket.get(key, 0) + amount


# ----------------------------------------------------------------------------
# Seeder
# ----------------------------------------------------------------------------
def seed_database(force: bool = False) -> SeedResult:
    """Populate the database with synthetic demo data.

    :param force: when True, drop and recreate every table before seeding.
    :returns: a :class:`SeedResult` describing what was created.
    """
    import app.models  # noqa: F401  (ensure all models are registered)

    db.create_all()

    if not force and db.session.query(AnganwadiCentre.id).first() is not None:
        return SeedResult(skipped=True)

    if force:
        db.drop_all()
        db.create_all()

    random.seed(RANDOM_SEED)
    created: dict[str, int] = {}

    # --- Centres -----------------------------------------------------------
    centres: list[AnganwadiCentre] = []
    for name, code, village, district, state, pincode, phone in CENTRES:
        centre = AnganwadiCentre(
            name=name, code=code, address=f"{village}, {district}",
            village=village, district=district, state=state,
            pincode=pincode, phone=phone, is_active=True,
        )
        centres.append(centre)
    db.session.add_all(centres)
    db.session.flush()
    _count(created, "anganwadi_centres", len(centres))

    # --- Users -------------------------------------------------------------
    users: list[User] = []

    admin = User(full_name="System Administrator", username="admin",
                 email="admin@poshansathi.demo", role=UserRole.ADMIN,
                 phone="9000010001")
    admin.set_password(DEMO_PASSWORD)
    users.append(admin)

    officer = User(full_name="District Programme Officer", username="officer",
                   email="officer@poshansathi.demo", role=UserRole.OFFICER,
                   phone="9000010002")
    officer.set_password(DEMO_PASSWORD)
    users.append(officer)

    for index in range(2):
        supervisor = User(
            full_name=f"Supervisor {index + 1}", username=f"supervisor{index + 1}",
            email=f"supervisor{index + 1}@poshansathi.demo",
            role=UserRole.SUPERVISOR, centre=centres[index], phone="9000010010",
        )
        supervisor.set_password(DEMO_PASSWORD)
        users.append(supervisor)

    awws: list[User] = []
    for index in range(10):
        centre = centres[index % len(centres)]
        aww = User(
            full_name=f"Anganwadi Worker {index + 1}", username=f"aww{index + 1}",
            email=f"aww{index + 1}@poshansathi.demo", role=UserRole.AWW,
            centre=centre, phone=f"90000200{index + 1:02d}",
        )
        aww.set_password(DEMO_PASSWORD)
        awws.append(aww)
        users.append(aww)

    db.session.add_all(users)
    db.session.flush()
    _count(created, "users", len(users))

    # --- Nutrition items and schemes --------------------------------------
    items = [NutritionItem(name=n, category=c, unit=u, description=d)
             for n, c, u, d in NUTRITION_ITEMS]
    db.session.add_all(items)
    _count(created, "nutrition_items", len(items))

    schemes = []
    for (name, category, target, benefits, eligibility, docs, application,
         note) in SCHEMES:
        schemes.append(WelfareScheme(
            name=name, category=category, description=note, target_group=target,
            benefits=benefits, eligibility=eligibility,
            required_documents=docs, application_info=application, is_active=True,
        ))
    db.session.add_all(schemes)
    db.session.flush()
    _count(created, "welfare_schemes", len(schemes))

    # --- Beneficiaries (children + mothers) --------------------------------
    beneficiaries: list[Beneficiary] = []
    children: list[Child] = []
    mothers: list[Mother] = []

    for c_index, centre in enumerate(centres):
        # Children
        for _ in range(20):
            gender = random.choice([Gender.MALE, Gender.FEMALE])
            age_days = random.randint(90, 1800)
            dob = TODAY - timedelta(days=age_days)
            guardian_gender = random.choice([Gender.MALE, Gender.FEMALE])
            beneficiary = Beneficiary(
                centre=centre, beneficiary_type=BeneficiaryType.CHILD,
                full_name=_random_name(gender), date_of_birth=dob, gender=gender,
                guardian_name=_random_name(guardian_gender),
                contact=_random_contact(), address=_random_address(c_index),
                status=RecordStatus.ACTIVE,
                registration_date=dob + timedelta(days=random.randint(1, 30)),
            )
            child = Child(
                beneficiary=beneficiary,
                birth_weight_kg=Decimal(str(round(random.uniform(2.2, 3.8), 2))),
                birth_height_cm=Decimal(str(round(random.uniform(45, 53), 1))),
                blood_group=random.choice([None, "A+", "B+", "O+", "AB+"]),
            )
            beneficiaries.append(beneficiary)
            children.append(child)

        # Pregnant women
        for _ in range(4):
            dob = TODAY - timedelta(days=random.randint(19 * 365, 40 * 365))
            month = random.randint(1, 8)
            beneficiary = Beneficiary(
                centre=centre, beneficiary_type=BeneficiaryType.PREGNANT_WOMAN,
                full_name=_random_name(Gender.FEMALE), date_of_birth=dob,
                gender=Gender.FEMALE, guardian_name=_random_name(Gender.MALE),
                contact=_random_contact(), address=_random_address(c_index),
                status=RecordStatus.ACTIVE,
                registration_date=TODAY - timedelta(days=random.randint(5, 120)),
            )
            mother = Mother(
                beneficiary=beneficiary, age=random.randint(19, 38),
                husband_name=_random_name(Gender.MALE),
                pregnancy_number=random.randint(1, 4),
                last_menstrual_period=TODAY - timedelta(days=month * 30),
                expected_delivery_date=TODAY + timedelta(days=(9 - month) * 30),
                blood_group=random.choice(["A+", "B+", "O+", "AB+"]),
                height_cm=Decimal(str(round(random.uniform(145, 165), 1))),
                current_risk_level=random.choice(
                    [RiskLevel.LOW, RiskLevel.LOW, RiskLevel.MODERATE]
                ),
            )
            beneficiaries.append(beneficiary)
            mothers.append(mother)

        # Lactating mothers
        for _ in range(4):
            dob = TODAY - timedelta(days=random.randint(19 * 365, 40 * 365))
            delivery = TODAY - timedelta(days=random.randint(20, 300))
            beneficiary = Beneficiary(
                centre=centre, beneficiary_type=BeneficiaryType.LACTATING_MOTHER,
                full_name=_random_name(Gender.FEMALE), date_of_birth=dob,
                gender=Gender.FEMALE, guardian_name=_random_name(Gender.MALE),
                contact=_random_contact(), address=_random_address(c_index),
                status=RecordStatus.ACTIVE, registration_date=delivery,
            )
            mother = Mother(
                beneficiary=beneficiary, age=random.randint(19, 38),
                husband_name=_random_name(Gender.MALE),
                pregnancy_number=random.randint(1, 4), delivery_date=delivery,
                blood_group=random.choice(["A+", "B+", "O+", "AB+"]),
                height_cm=Decimal(str(round(random.uniform(145, 165), 1))),
                current_risk_level=RiskLevel.LOW,
            )
            beneficiaries.append(beneficiary)
            mothers.append(mother)

    db.session.add_all(beneficiaries)
    db.session.flush()
    _count(created, "beneficiaries", len(beneficiaries))
    _count(created, "children", len(children))
    _count(created, "mothers", len(mothers))

    # Link the first two children of each centre to its lactating mothers.
    for c_index in range(len(centres)):
        centre_children = children[c_index * 20:(c_index + 1) * 20]
        centre_lactating = [
            m for m in mothers
            if m.beneficiary.centre_id == centres[c_index].id
            and m.beneficiary.beneficiary_type == BeneficiaryType.LACTATING_MOTHER
        ]
        for child, mother in zip(centre_children, centre_lactating):
            child.mother = mother

    # --- Growth, vaccinations, attendance, maternal health ----------------
    growth_records: list[GrowthRecord] = []
    vaccinations: list[Vaccination] = []
    attendance_records: list[Attendance] = []

    for c_index, centre in enumerate(centres):
        worker = awws[c_index % len(awws)]
        centre_children = children[c_index * 20:(c_index + 1) * 20]

        for child in centre_children:
            age_years = max(
                0.5, (TODAY - child.beneficiary.date_of_birth).days / 365.0
            )
            for i in range(3):
                measurement_date = TODAY - timedelta(days=90 * i + random.randint(0, 10))
                weight = round(3.0 + age_years * 2.2 + (2 - i) * 0.4, 2)
                height = round(50 + age_years * 7.0 + (2 - i) * 1.0, 2)
                growth_records.append(GrowthRecord(
                    child=child, recorded_by=worker,
                    measurement_date=measurement_date,
                    weight_kg=Decimal(str(weight)),
                    height_cm=Decimal(str(height)),
                    muac_cm=Decimal(str(round(random.uniform(11.5, 16.0), 1))),
                    nutritional_status=random.choice(GROWTH_STATUSES),
                    notes="Synthetic demo measurement.",
                ))

            for vaccine_name, dose, offset_days in VACCINE_SCHEDULE[:3]:
                scheduled = child.beneficiary.date_of_birth + timedelta(days=offset_days)
                if scheduled < TODAY - timedelta(days=30):
                    status = random.choice(
                        [VaccinationStatus.COMPLETED, VaccinationStatus.COMPLETED,
                         VaccinationStatus.MISSED]
                    )
                else:
                    status = random.choice(
                        [VaccinationStatus.UPCOMING, VaccinationStatus.DUE]
                    )
                vaccinations.append(Vaccination(
                    child=child, vaccine_name=vaccine_name, dose_number=dose,
                    scheduled_date=scheduled,
                    administered_date=scheduled if status == VaccinationStatus.COMPLETED else None,
                    status=status,
                    administered_by=worker if status == VaccinationStatus.COMPLETED else None,
                ))

            for day in range(5):
                attendance_date = TODAY - timedelta(days=day)
                attendance_records.append(Attendance(
                    child=child, centre=centre, attendance_date=attendance_date,
                    status=random.choices(
                        [AttendanceStatus.PRESENT, AttendanceStatus.ABSENT],
                        weights=[85, 15],
                    )[0],
                    recorded_by=worker,
                ))

    db.session.add_all(growth_records)
    db.session.add_all(vaccinations)
    db.session.add_all(attendance_records)
    _count(created, "growth_records", len(growth_records))
    _count(created, "vaccinations", len(vaccinations))
    _count(created, "attendance", len(attendance_records))

    maternal_records: list[MaternalHealthRecord] = []
    for m_index, mother in enumerate(mothers):
        worker = awws[m_index % len(awws)]
        for i in range(2):
            visit_date = TODAY - timedelta(days=30 * i + 5)
            maternal_records.append(MaternalHealthRecord(
                mother=mother, recorded_by=worker, visit_date=visit_date,
                pregnancy_month=random.randint(1, 9),
                weight_kg=Decimal(str(round(random.uniform(48, 72), 1))),
                haemoglobin=Decimal(str(round(random.uniform(8.5, 13.0), 1))),
                systolic_bp=random.randint(100, 140),
                diastolic_bp=random.randint(60, 95),
                risk_category=mother.current_risk_level,
                next_follow_up_date=visit_date + timedelta(days=30),
                notes="Synthetic ANC record.",
            ))
    db.session.add_all(maternal_records)
    _count(created, "maternal_health_records", len(maternal_records))

    # --- Inventory and distributions --------------------------------------
    inventories: list[Inventory] = []
    for c_index, centre in enumerate(centres):
        for i_index, item in enumerate(items):
            received = Decimal(str(round(random.uniform(20, 120), 2)))
            distributed = Decimal(str(round(random.uniform(0, 15), 2)))
            minimum = Decimal("25.00")
            # Make the first item at the first centre a low-stock example.
            if c_index == 0 and i_index == 0:
                received = Decimal("5.00")
                distributed = Decimal("0.00")
                minimum = Decimal("25.00")
            inventories.append(Inventory(
                centre=centre, item=item, opening_stock=Decimal("0.00"),
                received_quantity=received, distributed_quantity=distributed,
                minimum_stock=minimum, unit=item.unit,
                received_date=TODAY - timedelta(days=random.randint(10, 60)),
                expiry_date=TODAY + timedelta(days=random.randint(60, 365)),
            ))
    db.session.add_all(inventories)
    _count(created, "inventory", len(inventories))

    distributions: list[NutritionDistribution] = []
    for c_index, centre in enumerate(centres):
        worker = awws[c_index % len(awws)]
        centre_beneficiaries = [
            b for b in beneficiaries if b.centre_id == centre.id
        ]
        for _ in range(3):
            distributions.append(NutritionDistribution(
                beneficiary=random.choice(centre_beneficiaries),
                item=random.choice(items), centre=centre, worker=worker,
                quantity=Decimal(str(round(random.uniform(1, 5), 2))),
                distribution_date=TODAY - timedelta(days=random.randint(1, 30)),
                notes="Synthetic distribution record.",
            ))
    db.session.add_all(distributions)
    _count(created, "nutrition_distributions", len(distributions))

    # --- Scheme links ------------------------------------------------------
    scheme_links: list[BeneficiaryScheme] = []
    for c_index, centre in enumerate(centres):
        centre_beneficiaries = [
            b for b in beneficiaries if b.centre_id == centre.id
        ]
        for beneficiary in random.sample(centre_beneficiaries, 5):
            scheme_links.append(BeneficiaryScheme(
                beneficiary=beneficiary, scheme=random.choice(schemes),
                status=random.choice(
                    [SchemeStatus.ELIGIBLE, SchemeStatus.APPLIED,
                     SchemeStatus.ENROLLED]
                ),
                applied_date=TODAY - timedelta(days=random.randint(1, 90)),
            ))
    db.session.add_all(scheme_links)
    _count(created, "beneficiary_schemes", len(scheme_links))

    # --- Home visits and interventions ------------------------------------
    visits: list[HomeVisit] = []
    interventions: list[Intervention] = []
    for c_index, centre in enumerate(centres):
        worker = awws[c_index % len(awws)]
        centre_beneficiaries = [
            b for b in beneficiaries if b.centre_id == centre.id
        ]
        completed_beneficiary = random.choice(centre_beneficiaries)
        completed_visit = HomeVisit(
            beneficiary=completed_beneficiary, centre=centre,
            visit_type=VisitType.GROWTH, assigned_worker=worker,
            created_by=worker, scheduled_date=TODAY - timedelta(days=7),
            completed_date=TODAY - timedelta(days=6),
            status=VisitStatus.COMPLETED,
            visit_notes="Synthetic completed home visit.",
            follow_up_required=False,
        )
        visits.append(completed_visit)

        scheduled_visit = HomeVisit(
            beneficiary=random.choice(centre_beneficiaries), centre=centre,
            visit_type=VisitType.MATERNAL, assigned_worker=worker,
            created_by=worker, scheduled_date=TODAY + timedelta(days=3),
            status=VisitStatus.SCHEDULED,
            visit_notes="Synthetic scheduled home visit.",
            follow_up_required=True,
            follow_up_date=TODAY + timedelta(days=10),
        )
        visits.append(scheduled_visit)
        db.session.add(completed_visit)
        db.session.add(scheduled_visit)
        db.session.flush()

        intervention = Intervention(
            home_visit=completed_visit, beneficiary=completed_beneficiary,
            recorded_by=worker, intervention_type="Nutrition counselling",
            description="Advised the family on age-appropriate feeding.",
            outcome="Family counselled; follow-up not required.",
            intervention_date=TODAY - timedelta(days=6),
        )
        interventions.append(intervention)
        db.session.add(intervention)
    db.session.flush()
    _count(created, "home_visits", len(visits))
    _count(created, "interventions", len(interventions))

    # --- Alerts ------------------------------------------------------------
    alerts: list[Alert] = []
    alert_specs = [
        (AlertType.GROWTH_FOLLOW_UP, AlertSeverity.HIGH, AlertStatus.OPEN),
        (AlertType.VACCINATION_FOLLOW_UP, AlertSeverity.MEDIUM, AlertStatus.IN_PROGRESS),
        (AlertType.MATERNAL_FOLLOW_UP, AlertSeverity.MEDIUM, AlertStatus.RESOLVED),
        (AlertType.LOW_NUTRITION_STOCK, AlertSeverity.HIGH, AlertStatus.OPEN),
        (AlertType.ATTENDANCE, AlertSeverity.LOW, AlertStatus.DISMISSED),
    ]
    for c_index, centre in enumerate(centres):
        worker = awws[c_index % len(awws)]
        centre_children = [ch for ch in children if ch.beneficiary.centre_id == centre.id]
        for alert_type, severity, status in alert_specs:
            child = random.choice(centre_children)
            resolved = status in (AlertStatus.RESOLVED, AlertStatus.DISMISSED)
            alerts.append(Alert(
                beneficiary=child.beneficiary, child=child, alert_type=alert_type,
                severity=severity,
                message=f"Demo alert: {alert_type.value.replace('_', ' ').title()}.",
                status=status, assigned_to=worker, created_by=worker,
                resolved_at=datetime.utcnow() if resolved else None,
                resolution_notes="Synthetic resolution." if resolved else None,
            ))
    db.session.add_all(alerts)
    _count(created, "alerts", len(alerts))

    # --- Notifications -----------------------------------------------------
    notifications: list[Notification] = []
    for aww in awws:
        for title, category in [
            ("Vaccination due tomorrow", "VACCINATION"),
            ("Home visit pending", "HOME_VISIT"),
        ]:
            notifications.append(Notification(
                user=aww, title=title,
                message=f"Demo notification: {title.lower()}.",
                category=category, related_type=None, related_id=None,
                is_read=False,
            ))
    db.session.add_all(notifications)
    _count(created, "notifications", len(notifications))

    # --- Audit logs --------------------------------------------------------
    audit_logs = [
        AuditLog(user=admin, action="SEED_DATABASE", entity_type="Database",
                 details="Synthetic demo data inserted.", ip_address="127.0.0.1"),
        AuditLog(user=awws[0], action="CREATE_BENEFICIARY",
                 entity_type="Beneficiary", entity_id=1,
                 details="Demo record created by seeder.", ip_address="127.0.0.1"),
    ]
    db.session.add_all(audit_logs)
    _count(created, "audit_logs", len(audit_logs))

    db.session.commit()
    return SeedResult(created=created)


if __name__ == "__main__":  # pragma: no cover - manual execution
    from app import create_app

    app = create_app()
    with app.app_context():
        result = seed_database()
        print(result.summary())
