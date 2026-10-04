# PoshanSathi — Database

Phase 1 delivers the complete database foundation for PoshanSathi.

## Contents

| File | Purpose |
| --- | --- |
| `schema.sql` | Canonical raw-SQL MySQL schema (tables, foreign keys, indexes, timestamps). |
| `seed.py` | Synthetic demo-data seeder (fictional data only). |
| `__init__.py` | Makes `database` importable (`python -m database.seed`). |

## Configuration

The connection string comes from the environment (`.env`), never from code:

```env
DATABASE_URL=mysql+pymysql://poshansathi:poshansathi@localhost:3306/poshansathi
TEST_DATABASE_URL=sqlite:///:memory:
```

`config.py` reads `DATABASE_URL` for development/production and
`TEST_DATABASE_URL` for the automated tests (in-memory SQLite, so tests do not
require MySQL).

## Creating the schema

First, if the database/user do not exist yet, run the bootstrap helper as a
MySQL administrator:

```bash
sudo mysql < database/setup_mysql.sql
```

Preferred way to create the tables (stays in sync with the SQLAlchemy models):

```bash
flask --app app.py init-db     # create all tables
flask --app app.py seed-db     # insert synthetic demo data
```

Or apply the raw SQL directly:

```bash
mysql -u <user> -p < database/schema.sql
```

Destructive helpers:

```bash
flask --app app.py reset-db          # drop + recreate (no data)
flask --app app.py seed-db --force   # drop + recreate + seed
```

## Demo accounts

All seeded accounts use the password `password123`:

| Username | Role |
| --- | --- |
| `admin` | ADMIN |
| `officer` | OFFICER |
| `supervisor1`, `supervisor2` | SUPERVISOR |
| `aww1` … `aww10` | AWW |

## Tables

`anganwadi_centres`, `users`, `beneficiaries`, `mothers`, `children`,
`growth_records`, `vaccinations`, `maternal_health_records`, `nutrition_items`,
`inventory`, `nutrition_distributions`, `attendance`, `welfare_schemes`,
`beneficiary_schemes`, `home_visits`, `interventions`, `alerts`,
`notifications`, `audit_logs`.

Feature routes and UI are intentionally **not** part of Phase 1. They are added
in later phases, reusing these models.
