# PoshanSathi — Master Project Plan

> **Project:** PoshanSathi – Smart Nutrition & Welfare Tracking System for Anganwadi Centres  
> **Type:** College team project / demonstration system  
> **Primary stack:** Python + Flask + MySQL + Bootstrap 5 + JavaScript + Chart.js  
> **AI layer:** OpenRouter (optional, added only after the core application works)  
> **Development environment:** VS Code / OpenCode Desktop + Git  
> **Rule:** Build incrementally. Never ask the coding agent to implement the entire project in one step.

---

## 1. Project Vision

PoshanSathi is a web-based system for digitising selected Anganwadi-centre workflows around beneficiary registration, child growth tracking, maternal health, vaccination, nutrition distribution, attendance, welfare-scheme information, alerts, home visits, dashboards and reports.

The application is a **college demonstration/prototype**, not an official Government of India platform.

Use **synthetic/demo data only**.

The system should demonstrate one connected workflow:

```text
Worker Login
    ↓
Register Beneficiary
    ↓
Create Child / Mother Profile
    ↓
Record Health / Growth / Vaccination / Nutrition Data
    ↓
Business Rules Evaluate the Record
    ↓
Alert or Follow-up Created (when applicable)
    ↓
Worker Schedules Home Visit
    ↓
Records Intervention / Follow-up
    ↓
Supervisor Dashboard Updates
    ↓
Reports Generated
```

---

# 2. Development Philosophy

## 2.1 Spec-in-the-repo

`PROJECT_PLAN.md` is the persistent source of truth for the coding agent.

The agent must:

1. Read this file before starting a major task.
2. Inspect the current repository before modifying files.
3. Work only on the requested phase.
4. Avoid implementing future phases unless explicitly asked.
5. Reuse existing architecture instead of creating duplicate systems.
6. Run tests/sanity checks after implementation.
7. Report files changed and verification performed.

## 2.2 Never build everything at once

Do not issue a prompt such as:

> "Build the entire PoshanSathi application."

Instead:

```text
Plan → Foundation → Database → Auth → Beneficiaries
→ Health modules → Alerts/Visits → Dashboard
→ Reports → Testing → AI → Final polish
```

## 2.3 Git safety

Create a Git commit after every stable phase.

Recommended branches:

```text
main
develop

feature/auth
feature/beneficiaries
feature/growth
feature/vaccination
feature/maternal
feature/nutrition
feature/attendance
feature/schemes
feature/alerts
feature/visits
feature/dashboard
feature/reports
feature/ai
```

Do not use `git reset --hard` casually. Prefer reverting a bad commit or restoring the affected files after inspection. Never delete uncommitted team work without checking `git status` first.

---

# 3. Scope

## 3.1 MUST BUILD

- Authentication
- Role-based authorization
- Anganwadi centre management
- Beneficiary management
- Child profiles
- Pregnant/lactating mother profiles
- Child growth records
- Vaccination records
- Maternal health records
- Nutrition inventory
- Nutrition distribution
- Attendance
- Welfare-scheme information
- Rule-based alerts
- Home visits
- Interventions/follow-up
- Worker dashboard
- Supervisor dashboard
- Search/filtering
- Synthetic demo data
- Reports
- Basic automated tests
- Responsive frontend

## 3.2 SHOULD BUILD

- PDF reports
- Excel/CSV exports
- Notification centre
- Centre comparison
- Advanced dashboard filters
- Low-stock alerts
- Audit/activity log
- Better empty/error/loading states

## 3.3 OPTIONAL

Only after the complete core application is stable:

- OpenRouter AI assistant
- AI-generated dashboard summaries
- AI-assisted scheme information
- AI-assisted general nutrition education

## 3.4 NOT IN CURRENT SCOPE

Do not implement unless explicitly approved:

- Aadhaar integration
- Real government APIs
- Real beneficiary data
- WhatsApp API
- SMS gateway
- Production medical diagnosis
- Production clinical decision-making
- Mobile application
- Offline synchronisation
- RAG/vector database
- Complex ML prediction
- Payment systems

---

# 4. Users and Roles

## ADMIN

Can manage:

- users
- centres
- schemes
- system configuration
- demo data

## AWW — Anganwadi Worker

Can:

- register beneficiaries
- manage child/mother profiles
- record growth
- record vaccinations
- record maternal health
- record nutrition distribution
- record attendance
- view/manage alerts
- schedule home visits
- record interventions
- generate permitted reports

## SUPERVISOR

Can:

- view multiple centres
- monitor beneficiaries
- view alerts
- monitor vaccination coverage
- monitor nutrition distribution
- compare centre-level metrics
- view reports
- monitor pending follow-ups

## OFFICER

Can:

- view higher-level aggregated dashboards
- view reports
- compare centres
- inspect non-sensitive demo analytics

---

# 5. Technology Stack

## Frontend

- HTML5
- CSS3
- Bootstrap 5
- Bootstrap Icons
- Vanilla JavaScript
- Chart.js
- Jinja2 templates

React is NOT required for the initial project.

## Backend

- Python
- Flask
- Flask application factory
- Flask sessions
- SQLAlchemy / Flask-SQLAlchemy
- Werkzeug password hashing
- python-dotenv
- server-side validation

## Database

- MySQL

## Reports

Use appropriate Python libraries for:

- PDF
- XLSX
- CSV

## AI

- OpenRouter API
- Backend-only API access
- Model selected through environment variables

---

# 6. Architecture

```text
┌─────────────────────────────────────────────┐
│                 FRONTEND                    │
│ HTML + Jinja2 + Bootstrap + JS + Chart.js  │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│                  FLASK                      │
│ Routes → Services → Validation → Models     │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│                  MYSQL                      │
│ Users / Beneficiaries / Health / Reports    │
└─────────────────────────────────────────────┘

Optional:
Flask AI Service → OpenRouter → Selected Model
```

### Layer responsibilities

**Routes**
- receive HTTP requests
- authenticate/authorize
- validate request input
- call services
- render templates / return JSON where needed

**Services**
- business logic
- alert evaluation
- report preparation
- calculations
- AI integration

**Models**
- database entities and relationships

**Templates**
- presentation only

**Static JS**
- charts
- client-side interactions
- UI behaviour

Do not place large business-logic blocks directly inside templates.

---

# 7. Final Folder Structure

```text
PoshanSathi/
│
├── PROJECT_PLAN.md
├── README.md
├── app.py
├── config.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
│
├── database/
│   ├── schema.sql
│   ├── seed.py
│   └── README.md
│
├── app/
│   ├── __init__.py
│   ├── extensions.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── centre.py
│   │   ├── beneficiary.py
│   │   ├── child.py
│   │   ├── mother.py
│   │   ├── growth.py
│   │   ├── maternal_health.py
│   │   ├── vaccination.py
│   │   ├── nutrition.py
│   │   ├── attendance.py
│   │   ├── scheme.py
│   │   ├── home_visit.py
│   │   ├── intervention.py
│   │   ├── alert.py
│   │   ├── notification.py
│   │   └── audit_log.py
│   │
│   ├── routes/
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── centres.py
│   │   ├── beneficiaries.py
│   │   ├── children.py
│   │   ├── growth.py
│   │   ├── vaccination.py
│   │   ├── maternal.py
│   │   ├── nutrition.py
│   │   ├── attendance.py
│   │   ├── schemes.py
│   │   ├── visits.py
│   │   ├── alerts.py
│   │   ├── reports.py
│   │   └── ai.py
│   │
│   ├── services/
│   │   ├── alert_service.py
│   │   ├── growth_service.py
│   │   ├── vaccination_service.py
│   │   ├── nutrition_service.py
│   │   ├── scheme_service.py
│   │   ├── report_service.py
│   │   └── ai_service.py
│   │
│   ├── utils/
│   │   ├── decorators.py
│   │   ├── validators.py
│   │   ├── helpers.py
│   │   └── constants.py
│   │
│   ├── templates/
│   │   ├── base.html
│   │   ├── components/
│   │   │   ├── navbar.html
│   │   │   ├── sidebar.html
│   │   │   ├── flash_messages.html
│   │   │   ├── metric_card.html
│   │   │   └── pagination.html
│   │   │
│   │   ├── auth/
│   │   ├── dashboard/
│   │   ├── centres/
│   │   ├── beneficiaries/
│   │   ├── children/
│   │   ├── growth/
│   │   ├── vaccination/
│   │   ├── maternal/
│   │   ├── nutrition/
│   │   ├── attendance/
│   │   ├── schemes/
│   │   ├── visits/
│   │   ├── alerts/
│   │   ├── reports/
│   │   └── ai/
│   │
│   └── static/
│       ├── css/
│       │   ├── style.css
│       │   ├── dashboard.css
│       │   └── forms.css
│       ├── js/
│       │   ├── app.js
│       │   ├── dashboard.js
│       │   ├── beneficiaries.js
│       │   ├── growth.js
│       │   ├── vaccination.js
│       │   └── charts.js
│       └── img/
│
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_beneficiaries.py
│   ├── test_growth.py
│   ├── test_vaccination.py
│   ├── test_maternal.py
│   ├── test_nutrition.py
│   ├── test_alerts.py
│   ├── test_visits.py
│   └── test_dashboard.py
│
├── reports/
└── docs/
    ├── architecture.md
    ├── database.md
    ├── api.md
    ├── testing.md
    └── demo_script.md
```

Do not create empty feature files merely to match the tree. Create modules when their phase begins.

---

# 8. Database Design

Core tables:

```text
users
anganwadi_centres

beneficiaries
children
mothers

growth_records
maternal_health_records
vaccinations

nutrition_items
inventory
nutrition_distributions

attendance

welfare_schemes
beneficiary_schemes

home_visits
interventions

alerts
notifications
audit_logs
```

## Main relationship

```text
Centre
  ├── Users
  └── Beneficiaries
        ├── Child
        │    ├── Growth Records
        │    ├── Vaccinations
        │    ├── Attendance
        │    ├── Nutrition Distribution
        │    ├── Alerts
        │    └── Home Visits
        │
        └── Mother
             ├── Maternal Health
             ├── Scheme Links
             └── Home Visits
```

Use:

- primary keys
- foreign keys
- indexes for frequent searches
- timestamps
- sensible uniqueness constraints
- nullable fields only when genuinely optional

Do not store secrets or API keys in the database.

---

# 9. Core Business Workflow

The application must support this complete demonstrable workflow:

```text
AWW Login
   ↓
Register Child
   ↓
Open Child Profile
   ↓
Add Monthly Growth Record
   ↓
Evaluate configured growth rules
   ↓
Create Alert if required
   ↓
Schedule Home Visit
   ↓
Record Visit + Intervention
   ↓
Schedule Follow-up
   ↓
Resolve Alert
   ↓
Dashboard Metrics Update
   ↓
Generate Report
```

This is the primary integration test and demo story.

---

# 10. Module Specifications

## 10.1 Authentication

Features:

- login
- logout
- session management
- password hashing
- role checks
- unauthorized access handling
- login validation

Demo accounts must use hashed passwords.

---

## 10.2 Beneficiary Management

### Child

- name
- date of birth
- gender
- guardian name
- contact
- address
- centre
- birth weight
- registration date

### Pregnant Woman

- name
- age
- pregnancy information
- expected delivery date
- weight
- haemoglobin
- blood pressure
- risk status

### Lactating Mother

- name
- delivery date
- linked child where appropriate
- nutrition/health follow-up information

Features:

- create
- view
- update
- deactivate
- search
- filter
- detail page

---

## 10.3 Growth Tracking

Record:

- measurement date
- weight
- height
- MUAC

Display:

- history table
- weight trend
- height trend
- measurement timeline
- current configured status

Important:

Do not invent medical thresholds.

If official growth references are used, document the exact reference/source/version and implement age/sex-specific rules correctly.

For the college demo, the alert engine may initially use clearly documented **demo rules**, labelled as demonstration rules.

---

## 10.4 Vaccination

Track:

- vaccine name
- scheduled/due date
- administered date
- status
- notes

Statuses:

```text
UPCOMING
DUE
COMPLETED
MISSED
```

Do not invent an official immunization schedule. Store a verified schedule/configuration supplied by the project team.

---

## 10.5 Maternal Health

Track:

- ANC visit date
- pregnancy month
- weight
- haemoglobin
- blood pressure
- risk category
- next follow-up
- notes

Highlight configured follow-ups.

Do not use an LLM to make clinical risk decisions.

---

## 10.6 Nutrition

### Inventory

- item
- unit
- quantity
- minimum stock
- expiry date

### Distribution

- beneficiary
- item
- quantity
- date
- worker

Calculate:

```text
Current Stock =
Opening Stock + Received - Distributed
```

Create a low-stock alert when configured minimum stock is reached.

---

## 10.7 Attendance

Record:

- child
- date
- present/absent
- optional note

Display:

- daily attendance
- monthly percentage
- frequent absence list

---

## 10.8 Welfare Schemes

Store:

- scheme name
- description
- target group
- benefits
- eligibility information
- required documents
- application information

The system may show **potentially relevant schemes** based on configured profile rules.

Do not claim guaranteed government eligibility.

---

## 10.9 Alerts

Alert fields:

```text
id
beneficiary/child reference
type
severity
message
status
created_at
assigned_to
resolved_at
```

Statuses:

```text
OPEN
IN_PROGRESS
RESOLVED
DISMISSED
```

Types may include:

- growth follow-up
- vaccination follow-up
- maternal follow-up
- low nutrition stock
- attendance
- home visit pending

Alert rules must be explicit and testable.

---

## 10.10 Home Visits

Fields:

- beneficiary
- visit type
- assigned worker
- scheduled date
- status
- visit notes
- intervention
- follow-up date

Workflow:

```text
Scheduled
→ Completed
→ Intervention Recorded
→ Follow-up Required / Resolved
```

---

# 11. Dashboards

## AWW Dashboard

Display:

- total children
- pregnant women
- lactating mothers
- open alerts
- pending visits
- upcoming vaccinations
- recent registrations
- attendance summary
- nutrition stock status

## Supervisor Dashboard

Display:

- total centres
- total children
- total mothers
- open alerts
- vaccination coverage
- nutrition distribution
- pending visits
- alert resolution
- centre comparison

All metrics must come from the database. Never hardcode dashboard numbers.

---

# 12. Reports

Required:

- child profile report
- child growth report
- vaccination report
- maternal health report
- nutrition distribution report
- monthly centre report
- scheme report

Formats:

- HTML printable view
- PDF
- CSV/XLSX where practical

---

# 13. Notifications

Initial implementation may be an in-app notification centre.

Examples:

- vaccination due
- follow-up due
- home visit due
- low stock
- unresolved alert

Do not implement SMS/WhatsApp unless explicitly approved.

---

# 14. AI Layer

AI is an optional layer and must never be required for the core application.

## Architecture

```text
Flask route
    ↓
AI service
    ↓
OpenRouter
    ↓
Configured model
```

Environment:

```env
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
```

The key must remain server-side.

## AI features

### Nutrition information assistant

Provides general educational information and clearly avoids diagnosis.

### Scheme information assistant

Uses the application's configured scheme data as the source of truth.

### Dashboard summary

The backend computes real metrics first. AI may convert those metrics into natural-language summaries.

Never send unnecessary personal or sensitive beneficiary data to the model.

---

# 15. Demo Data

Create synthetic data with `database/seed.py`.

Suggested demo size:

```text
5 centres
10 AWW users
2 supervisors
1 admin
100 children
20 pregnant women
20 lactating mothers

300+ growth records
vaccination records
attendance records
nutrition distributions
home visits
alerts
```

All names, contacts and addresses must be fictional.

Seed data should create a realistic dashboard with:

- normal cases
- pending cases
- resolved alerts
- upcoming visits
- upcoming vaccinations
- low-stock example

---

# 16. Frontend Design Rules

Use one consistent design system:

- Bootstrap 5
- Bootstrap Icons
- responsive layout
- sidebar + top navigation
- reusable cards
- reusable tables
- consistent forms
- clear status badges
- confirmation dialogs
- validation messages
- empty states
- loading states
- error states

The interface should feel like one product, not separate student modules.

---

# 17. Security Rules

- Never hardcode API keys.
- Never expose OpenRouter keys to browser JavaScript.
- Hash passwords.
- Validate input server-side.
- Use parameterized queries/ORM.
- Protect routes by role.
- Escape/render user content safely.
- Do not use real beneficiary information.
- Do not log secrets.
- Do not commit `.env`.

`.gitignore` must contain:

```text
.env
.venv/
__pycache__/
*.pyc
```

---

# 18. Testing Strategy

Every phase should include relevant tests.

## Unit tests

- validation
- services
- alert rules
- calculations

## Route tests

- authentication
- authorization
- CRUD
- invalid input
- redirects

## Integration tests

At minimum:

```text
Register child
→ Add growth record
→ Alert generated
→ Schedule visit
→ Complete visit
→ Dashboard updated
```

## Final acceptance test

A clean demo environment must allow the complete workflow to run without manual database editing.

---

# 19. Development Phases

## Phase 0 — Repository and Foundation

Deliver:

- Flask app
- application factory
- configuration
- environment handling
- requirements
- base template
- Bootstrap
- project structure
- error handling
- Git baseline

No feature modules yet.

---

## Phase 1 — Database

Deliver:

- complete schema
- relationships
- indexes
- seed script foundation
- database connection
- demo users/centre data

No unnecessary feature routes.

---

## Phase 2 — Authentication

Deliver:

- login
- logout
- sessions
- password hashing
- roles
- decorators
- protected routes
- role-aware navigation

---

## Phase 3 — Beneficiaries

Deliver:

- child
- pregnant woman
- lactating mother
- list/search/filter
- create
- update
- detail
- deactivate

---

## Phase 4 — Growth

Deliver:

- growth records
- history
- validation
- charts
- service layer
- demo history

---

## Phase 5 — Vaccination

Deliver:

- vaccination records
- status
- due/upcoming/missed views
- history
- dashboard summary

---

## Phase 6 — Maternal Health

Deliver:

- ANC records
- maternal measurements
- follow-up dates
- history
- dashboard summary

---

## Phase 7 — Nutrition + Inventory

Deliver:

- items
- stock
- distribution
- stock calculations
- low-stock alerts
- reports

---

## Phase 8 — Attendance

Deliver:

- daily attendance
- monthly summary
- absence tracking
- dashboard metrics

---

## Phase 9 — Alerts + Home Visits

Deliver:

- alert service
- alert list
- status changes
- assignment
- home visits
- intervention
- follow-up

This phase connects the modules.

---

## Phase 10 — Welfare Schemes

Deliver:

- scheme catalogue
- beneficiary links
- profile-based potential matches
- scheme detail page

---

## Phase 11 — Dashboards

Deliver:

- AWW dashboard
- supervisor dashboard
- officer dashboard if needed
- charts
- centre comparison
- filters

---

## Phase 12 — Reports + Notifications

Deliver:

- PDF/CSV/XLSX where practical
- printable reports
- notification centre
- report filters

---

## Phase 13 — Testing + Integration

Deliver:

- unit tests
- route tests
- integration tests
- seed data
- error handling
- responsive testing
- security review
- final demo workflow

---

## Phase 14 — Optional AI + Final Polish

Only if core application is stable:

- OpenRouter service
- AI assistant
- graceful API failure handling
- prompt safety
- dashboard summaries
- final UI polish
- README
- architecture docs
- demo script
- PPT material

---

# 20. Golden Prompt Formula

Every OpenCode task should follow:

```text
1. Read PROJECT_PLAN.md.
2. Inspect the current repository.
3. Identify existing relevant files.
4. State the implementation plan briefly.
5. Implement ONLY the requested phase.
6. Do not modify unrelated modules.
7. Reuse existing components/services.
8. Run tests/sanity checks.
9. Fix errors caused by the implementation.
10. Report:
   - files created
   - files modified
   - database changes
   - tests run
   - remaining issues
```

---

# 21. Phase Prompts

## Prompt 0 — Understand Before Coding

```text
Read PROJECT_PLAN.md completely.

You are the lead developer for PoshanSathi.

Do NOT modify any files yet.

Inspect the current repository and report:

1. Current folder structure.
2. Existing files and their purpose.
3. Existing Python/Flask setup.
4. Existing database setup.
5. Existing frontend setup.
6. Whether Git is initialized.
7. Any conflicts between the current repository and PROJECT_PLAN.md.
8. A phase-by-phase implementation plan.

Do not create feature modules yet.
Do not delete existing work.
Do not implement the whole application.

Wait for the next phase instruction after producing the analysis.
```

## Prompt 1 — Foundation

```text
Read PROJECT_PLAN.md and inspect the current repository.

Implement ONLY Phase 0: Repository and Foundation.

Create the Flask application foundation, application factory,
configuration, environment handling, requirements.txt,
base.html, reusable layout structure, static directories,
error handling and basic logging.

Use SQLAlchemy/Flask-SQLAlchemy for the database layer unless
the existing project already has a working database architecture.

Do not implement feature modules.

Run a startup/sanity test and report all changed files.
```

## Prompt 2 — Database

```text
Read PROJECT_PLAN.md.

Implement ONLY Phase 1: Database.

Create the normalized MySQL schema for the planned modules,
including primary keys, foreign keys, indexes and timestamps.

Create/update database/schema.sql and database/seed.py.

Create only the database foundation and synthetic demo data.
Do not implement feature routes or UI.

Use the project database architecture consistently.
Do not invent table names later without updating the schema.

Verify that the schema can be created successfully and that
the seed script inserts valid demo records.
```

## Prompt 3 — Authentication

```text
Read PROJECT_PLAN.md and inspect the existing foundation.

Implement ONLY Phase 2: Authentication.

Implement:
- login
- logout
- password hashing
- sessions
- ADMIN
- AWW
- SUPERVISOR
- OFFICER
- login_required
- role_required
- protected routes
- role-aware navigation

Do not implement beneficiary or health modules.

Test valid login, invalid login and unauthorized access.
```

## Prompt 4 — Beneficiaries

```text
Read PROJECT_PLAN.md.

Implement ONLY Phase 3: Beneficiary Management.

Implement child, pregnant-woman and lactating-mother
registration/profile management using the existing database architecture.

Include:
- create
- list
- search
- filter
- detail
- update
- deactivate
- validation
- role protection

Do not redesign authentication or the database architecture unnecessarily.

Run route/database tests before finishing.
```

## Prompt 5 — Growth

```text
Read PROJECT_PLAN.md.

Implement ONLY Phase 4: Growth Tracking.

Implement:
- growth record creation
- validation
- history table
- child growth charts using Chart.js
- growth service
- demo historical records

Do not invent medical thresholds.

If a classification rule is needed, use only a configured,
documented project rule and clearly label demo rules as such.

Test normal, invalid and boundary inputs.
```

## Prompt 6 — Vaccination

```text
Read PROJECT_PLAN.md.

Implement ONLY Phase 5: Vaccination.

Implement:
- vaccination record
- vaccine status
- due/upcoming/missed/completed views
- vaccination history
- dashboard metrics

Use a configurable verified schedule rather than inventing
medical schedules.

Do not modify unrelated modules.
Run tests.
```

## Prompt 7 — Maternal Health

```text
Read PROJECT_PLAN.md.

Implement ONLY Phase 6: Maternal Health.

Implement:
- maternal profile data
- ANC records
- weight
- haemoglobin
- blood pressure
- follow-up date
- configured risk/follow-up status
- history page
- dashboard metrics

Do not use an LLM for clinical decision-making.
Do not invent clinical thresholds.

Run tests and report changes.
```

## Prompt 8 — Nutrition

```text
Read PROJECT_PLAN.md.

Implement ONLY Phase 7: Nutrition and Inventory.

Implement:
- nutrition item catalogue
- inventory
- stock received
- stock distributed
- current stock calculation
- beneficiary distribution records
- minimum-stock alert
- nutrition summary

Do not duplicate existing alert logic.
Reuse the alert service.

Run tests for stock calculations and invalid quantities.
```

## Prompt 9 — Attendance

```text
Read PROJECT_PLAN.md.

Implement ONLY Phase 8: Attendance.

Implement:
- daily attendance
- monthly summary
- present/absent status
- frequent absence view
- dashboard metric

Prevent duplicate attendance records for the same
child/date unless the business rule explicitly allows updates.

Run tests.
```

## Prompt 10 — Alerts + Visits

```text
Read PROJECT_PLAN.md.

Implement ONLY Phase 9: Alerts and Home Visits.

Create a centralized alert service.

Support:
- open
- in progress
- resolved
- dismissed

Support alert assignment and severity.

Implement:
- home visit scheduling
- assigned worker
- visit status
- visit notes
- intervention
- follow-up date

Integrate with existing growth, vaccination, maternal and
nutrition services without duplicating business logic.

Test the complete:
record → alert → visit → intervention → resolution workflow.
```

## Prompt 11 — Schemes

```text
Read PROJECT_PLAN.md.

Implement ONLY Phase 10: Welfare Schemes.

Create:
- scheme catalogue
- scheme detail
- beneficiary-scheme links
- profile-based potential matches using explicit configured rules

Do not claim guaranteed eligibility.
Do not use an LLM as the source of scheme eligibility.

Seed the system with clearly labelled demonstration scheme data.
```

## Prompt 12 — Dashboard

```text
Read PROJECT_PLAN.md.

Implement ONLY Phase 11: Dashboards.

Build:
- AWW dashboard
- Supervisor dashboard
- Officer dashboard if appropriate

All metrics must be calculated from the database.

Include:
- beneficiary counts
- open alerts
- pending visits
- vaccination metrics
- nutrition metrics
- attendance
- centre comparison
- charts where useful

Do not hardcode dashboard numbers.

Verify that different roles see appropriate data.
```

## Prompt 13 — Reports

```text
Read PROJECT_PLAN.md.

Implement ONLY Phase 12: Reports and Notifications.

Create:
- child report
- growth report
- vaccination report
- maternal report
- nutrition report
- monthly centre report
- scheme report

Provide printable HTML and practical CSV/XLSX/PDF exports
where supported by the current project.

Also implement the in-app notification centre.

Do not add SMS or WhatsApp integration.
```

## Prompt 14 — Testing + Integration

```text
Read PROJECT_PLAN.md.

Implement ONLY Phase 13: Testing and Integration.

Inspect the entire current project.

Do not rewrite working modules unnecessarily.

Create/fix:
- unit tests
- route tests
- authorization tests
- service tests
- integration tests

The most important integration test is:

register child
→ add growth record
→ configured alert generated
→ schedule home visit
→ complete visit
→ record intervention
→ resolve alert
→ dashboard reflects changes.

Run the full test suite.
Fix only verified issues.
Report all remaining failures clearly.
```

## Prompt 15 — AI

```text
Read PROJECT_PLAN.md.

Only proceed because the core application is already stable.

Implement ONLY the optional AI layer.

Use OpenRouter from the Flask backend.

Requirements:
- OPENROUTER_API_KEY from environment
- OPENROUTER_MODEL from environment
- never expose key to frontend
- graceful API failure
- timeout handling
- clear user-facing errors
- minimal necessary data sent to model

Implement:
1. General educational nutrition assistant.
2. Scheme information assistant using application data as source.
3. Optional dashboard summary using database-calculated metrics.

Do not allow AI to determine medical diagnosis,
vaccination schedules, or official scheme eligibility.

Add tests for missing API key and API failure.
```

---

# 22. Final Acceptance Checklist

Before declaring the project complete:

### Infrastructure

- [ ] Application starts
- [ ] MySQL connection works
- [ ] `.env` protected
- [ ] Git repository clean
- [ ] requirements documented

### Authentication

- [ ] Login works
- [ ] Logout works
- [ ] Roles work
- [ ] Unauthorized routes protected

### Beneficiaries

- [ ] Child registration
- [ ] Mother registration
- [ ] Search/filter
- [ ] Profile pages

### Health

- [ ] Growth
- [ ] Charts
- [ ] Vaccination
- [ ] Maternal health

### Nutrition

- [ ] Inventory
- [ ] Distribution
- [ ] Stock calculations
- [ ] Low-stock alert

### Operations

- [ ] Attendance
- [ ] Alerts
- [ ] Home visits
- [ ] Interventions
- [ ] Follow-up

### Information

- [ ] Schemes
- [ ] Notifications
- [ ] Reports

### Analytics

- [ ] Worker dashboard
- [ ] Supervisor dashboard
- [ ] Centre comparison
- [ ] Charts

### Quality

- [ ] Demo data
- [ ] Unit tests
- [ ] Integration tests
- [ ] Responsive UI
- [ ] Error handling
- [ ] No hardcoded secrets

### Optional

- [ ] OpenRouter AI
- [ ] AI failure handling
- [ ] AI safety constraints

---

# 23. Final Demo Scenario

Use one fictional beneficiary to demonstrate the complete workflow:

```text
Login as AWW
   ↓
Register child
   ↓
Open child profile
   ↓
Add growth measurement
   ↓
Show growth history/chart
   ↓
Show configured alert/follow-up
   ↓
Schedule home visit
   ↓
Complete visit
   ↓
Record intervention
   ↓
Resolve follow-up
   ↓
Open supervisor dashboard
   ↓
Show updated metrics
   ↓
Generate child/monthly report
   ↓
Optionally demonstrate AI assistant
```

This should be the main end-to-end demonstration.

---

# 24. Definition of Done

A phase is DONE only when:

1. The requested functionality works.
2. It integrates with the existing architecture.
3. Database changes are consistent with the schema.
4. The frontend is usable.
5. Validation exists.
6. Authorization is correct.
7. Relevant tests pass.
8. No unrelated modules were broken.
9. Demo data works.
10. A Git commit is created.

Do not mark a phase complete just because files were generated.

---

# 25. Project Success Criteria

The project succeeds when a new user can clone the repository,
configure MySQL and environment variables, seed the database,
start Flask, log in and demonstrate the complete beneficiary →
health record → alert → home visit → dashboard → report workflow
without manually editing database rows.

The application should be understandable to a beginner developer
and defensible during a college project viva.
