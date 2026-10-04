"""SQLite storage layer.

Everything the app persists lives in a single SQLite file, created on first
run.  The bundled ``data/foods.csv`` is used to seed the food table so the app
is useful immediately.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

# Keep the database next to the package so the project stays self-contained.
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "poshansathi.db"
FOODS_CSV = BASE_DIR / "data" / "foods.csv"

SCHEMA = """
CREATE TABLE IF NOT EXISTS foods (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    category      TEXT    NOT NULL,
    serving_desc  TEXT    NOT NULL,
    serving_grams REAL    NOT NULL DEFAULT 0,
    calories      REAL    NOT NULL,
    protein_g     REAL    NOT NULL DEFAULT 0,
    carbs_g       REAL    NOT NULL DEFAULT 0,
    fat_g         REAL    NOT NULL DEFAULT 0,
    fiber_g       REAL    NOT NULL DEFAULT 0,
    iron_mg       REAL    NOT NULL DEFAULT 0,
    calcium_mg    REAL    NOT NULL DEFAULT 0,
    vitamin_c_mg  REAL    NOT NULL DEFAULT 0,
    is_veg        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL,
    age            INTEGER NOT NULL,
    gender         TEXT    NOT NULL,
    height_cm      REAL    NOT NULL,
    weight_kg      REAL    NOT NULL,
    activity_level TEXT    NOT NULL,
    goal           TEXT    NOT NULL,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meal_entries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    entry_date TEXT    NOT NULL,
    meal_type  TEXT    NOT NULL,
    food_id    INTEGER NOT NULL,
    quantity   REAL    NOT NULL DEFAULT 1,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (food_id) REFERENCES foods(id)
);

CREATE INDEX IF NOT EXISTS idx_entries_user_date
    ON meal_entries (user_id, entry_date);
"""


def get_connection(db_path=None) -> sqlite3.Connection:
    """Open a connection with row access by column name."""
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None, db_path=None) -> sqlite3.Connection:
    """Create tables (if needed) and seed the food database.

    Safe to call repeatedly - existing data is left untouched.
    """
    conn = conn or get_connection(db_path)
    conn.executescript(SCHEMA)
    _seed_foods(conn)
    conn.commit()
    return conn


def _seed_foods(conn: sqlite3.Connection) -> int:
    """Load foods from the bundled CSV, skipping any that already exist."""
    if not FOODS_CSV.exists():
        return 0

    existing = {row["name"] for row in conn.execute("SELECT name FROM foods")}
    inserted = 0
    with FOODS_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["name"] in existing:
                continue
            conn.execute(
                """
                INSERT INTO foods
                    (name, category, serving_desc, serving_grams, calories,
                     protein_g, carbs_g, fat_g, fiber_g, iron_mg,
                     calcium_mg, vitamin_c_mg, is_veg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["name"], row["category"], row["serving_desc"],
                    float(row["serving_grams"] or 0), float(row["calories"]),
                    float(row["protein_g"]), float(row["carbs_g"]),
                    float(row["fat_g"]), float(row["fiber_g"]),
                    float(row["iron_mg"]), float(row["calcium_mg"]),
                    float(row["vitamin_c_mg"]), int(row["is_veg"]),
                ),
            )
            inserted += 1
    return inserted


def reset_db(db_path=None) -> sqlite3.Connection:
    """Delete and rebuild the database.  Handy while developing."""
    path = Path(db_path or DEFAULT_DB_PATH)
    if path.exists():
        path.unlink()
    return init_db(db_path=path)