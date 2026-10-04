"""User, food and meal-tracking operations.

This module is the main API the CLI and the web UI both sit on top of.  It
keeps SQL in one place and returns :mod:`poshansathi.models` objects.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from .models import Food, NutritionTotals, User

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------
def create_user(conn: sqlite3.Connection, name: str, age: int, gender: str,
                height_cm: float, weight_kg: float, activity_level: str,
                goal: str) -> int:
    """Insert a user and return the new id."""
    cur = conn.execute(
        """
        INSERT INTO users
            (name, age, gender, height_cm, weight_kg, activity_level, goal)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (name, age, gender, height_cm, weight_kg, activity_level, goal),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_user(conn: sqlite3.Connection, user_id: int) -> User | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return User.from_row(row) if row else None


def list_users(conn: sqlite3.Connection) -> list[User]:
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    return [User.from_row(r) for r in rows]


def update_user(conn: sqlite3.Connection, user_id: int, **fields) -> None:
    """Update any subset of a user's profile fields."""
    allowed = {"name", "age", "gender", "height_cm", "weight_kg",
               "activity_level", "goal"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    assignments = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE users SET {assignments} WHERE id = ?",
        (*updates.values(), user_id),
    )
    conn.commit()


# --------------------------------------------------------------------------
# Foods
# --------------------------------------------------------------------------
def _row_to_food(row: sqlite3.Row) -> Food:
    return Food(
        id=row["id"], name=row["name"], category=row["category"],
        serving_desc=row["serving_desc"], serving_grams=row["serving_grams"],
        calories=row["calories"], protein_g=row["protein_g"],
        carbs_g=row["carbs_g"], fat_g=row["fat_g"], fiber_g=row["fiber_g"],
        iron_mg=row["iron_mg"], calcium_mg=row["calcium_mg"],
        vitamin_c_mg=row["vitamin_c_mg"], is_veg=bool(row["is_veg"]),
    )


def get_food(conn: sqlite3.Connection, food_id: int) -> Food | None:
    row = conn.execute("SELECT * FROM foods WHERE id = ?", (food_id,)).fetchone()
    return _row_to_food(row) if row else None


def list_foods(conn: sqlite3.Connection, category: str | None = None) -> list[Food]:
    if category:
        rows = conn.execute(
            "SELECT * FROM foods WHERE category = ? ORDER BY name", (category,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM foods ORDER BY category, name").fetchall()
    return [_row_to_food(r) for r in rows]


def search_foods(conn: sqlite3.Connection, term: str) -> list[Food]:
    rows = conn.execute(
        "SELECT * FROM foods WHERE name LIKE ? ORDER BY name",
        (f"%{term}%",),
    ).fetchall()
    return [_row_to_food(r) for r in rows]


def list_categories(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT DISTINCT category FROM foods ORDER BY category")
    return [r["category"] for r in rows]


def add_food(conn: sqlite3.Connection, food: Food) -> int:
    """Add a custom food item (name must be unique)."""
    cur = conn.execute(
        """
        INSERT INTO foods
            (name, category, serving_desc, serving_grams, calories,
             protein_g, carbs_g, fat_g, fiber_g, iron_mg,
             calcium_mg, vitamin_c_mg, is_veg)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (food.name, food.category, food.serving_desc, food.serving_grams,
         food.calories, food.protein_g, food.carbs_g, food.fat_g, food.fiber_g,
         food.iron_mg, food.calcium_mg, food.vitamin_c_mg, int(food.is_veg)),
    )
    conn.commit()
    return int(cur.lastrowid)


# --------------------------------------------------------------------------
# Meal entries
# --------------------------------------------------------------------------
def log_meal(conn: sqlite3.Connection, user_id: int, entry_date: str,
             meal_type: str, food_id: int, quantity: float = 1.0) -> int:
    """Log ``quantity`` servings of ``food_id`` for a user."""
    if meal_type not in MEAL_TYPES:
        raise ValueError(f"meal_type must be one of {MEAL_TYPES}")
    cur = conn.execute(
        """
        INSERT INTO meal_entries (user_id, entry_date, meal_type, food_id, quantity)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, entry_date, meal_type, food_id, quantity),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_entries(conn: sqlite3.Connection, user_id: int,
                entry_date: str) -> list[dict]:
    """Return entries for a day, joined with food names, grouped logically."""
    rows = conn.execute(
        """
        SELECT e.id, e.meal_type, e.quantity, e.food_id,
               f.name AS food_name, f.serving_desc,
               f.calories, f.protein_g, f.carbs_g, f.fat_g,
               f.fiber_g, f.iron_mg, f.calcium_mg, f.vitamin_c_mg
        FROM meal_entries e
        JOIN foods f ON f.id = e.food_id
        WHERE e.user_id = ? AND e.entry_date = ?
        ORDER BY CASE e.meal_type
                    WHEN 'breakfast' THEN 1
                    WHEN 'lunch'     THEN 2
                    WHEN 'dinner'    THEN 3
                    ELSE 4 END, e.id
        """,
        (user_id, entry_date),
    ).fetchall()
    result = []
    for r in rows:
        item = dict(r)
        q = r["quantity"]
        item["total_calories"] = round(r["calories"] * q, 1)
        result.append(item)
    return result


def delete_entry(conn: sqlite3.Connection, entry_id: int) -> None:
    conn.execute("DELETE FROM meal_entries WHERE id = ?", (entry_id,))
    conn.commit()


def daily_totals(conn: sqlite3.Connection, user_id: int,
                 entry_date: str) -> NutritionTotals:
    """Sum all nutrition for a user on a given date."""
    rows = conn.execute(
        """
        SELECT f.*, e.quantity
        FROM meal_entries e
        JOIN foods f ON f.id = e.food_id
        WHERE e.user_id = ? AND e.entry_date = ?
        """,
        (user_id, entry_date),
    ).fetchall()
    totals = NutritionTotals()
    for r in rows:
        totals.add(_row_to_food(r), r["quantity"])
    return totals


def entries_between(conn: sqlite3.Connection, user_id: int,
                    start: str, end: str) -> list[dict]:
    """Return per-day totals between two ISO dates (inclusive)."""
    rows = conn.execute(
        """
        SELECT e.entry_date AS day, f.*, e.quantity
        FROM meal_entries e
        JOIN foods f ON f.id = e.food_id
        WHERE e.user_id = ? AND e.entry_date BETWEEN ? AND ?
        ORDER BY e.entry_date
        """,
        (user_id, start, end),
    ).fetchall()
    days: dict[str, dict] = {}
    for r in rows:
        day = r["day"]
        bucket = days.setdefault(day, {"date": day, "calories": 0.0,
                                       "protein_g": 0.0, "carbs_g": 0.0,
                                       "fat_g": 0.0})
        q = r["quantity"]
        bucket["calories"] += r["calories"] * q
        bucket["protein_g"] += r["protein_g"] * q
        bucket["carbs_g"] += r["carbs_g"] * q
        bucket["fat_g"] += r["fat_g"] * q
    for bucket in days.values():
        for key in ("calories", "protein_g", "carbs_g", "fat_g"):
            bucket[key] = round(bucket[key], 1)
    return [days[d] for d in sorted(days)]


def week_bounds(reference: date | None = None) -> tuple[str, str]:
    """Return ISO (monday, sunday) for the week containing ``reference``."""
    ref = reference or date.today()
    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def parse_date(value: str) -> date:
    """Parse an ISO date string, defaulting to today on empty input."""
    if not value:
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()