#!/usr/bin/env python3
"""Create a demo profile with a week of sample meals.

Useful for showing off the dashboard and weekly report without typing data in.
Run with ``python seed_demo.py`` or ``python main.py seed``.
"""

from __future__ import annotations

from datetime import date, timedelta

from poshansathi import database, tracker


# A one-day meal plan used for the most recent days, so the dashboard has data.
DAY_PLAN = {
    "breakfast": [("Oats (dry)", 1), ("Toned Milk", 1), ("Banana", 1)],
    "lunch": [("Roti (Chapati)", 3), ("Dal Tadka", 1), ("Green Salad", 1)],
    "snack": [("Chai with Sugar", 1), ("Almonds", 2)],
    "dinner": [("Plain Rice (cooked)", 1), ("Mixed Veg Sabzi", 1), ("Curd (Dahi)", 1)],
}


def _food_id(conn, name: str) -> int | None:
    for food in tracker.search_foods(conn, name):
        if food.name == name:
            return food.id
    return None


def seed(days: int = 7) -> int:
    conn = database.init_db()

    user_id = tracker.create_user(
        conn,
        name="Demo User",
        age=24,
        gender="female",
        height_cm=163,
        weight_kg=58,
        activity_level="moderate",
        goal="maintain",
    )

    today = date.today()
    logged = 0
    for offset in range(days):
        day = (today - timedelta(days=offset)).isoformat()
        for meal, items in DAY_PLAN.items():
            for name, qty in items:
                fid = _food_id(conn, name)
                if fid:
                    tracker.log_meal(conn, user_id, day, meal, fid, qty)
                    logged += 1

    print(f"Seeded demo profile #{user_id} with {logged} meal entries "
          f"over {days} day(s).")
    print("Try:  python main.py web   ->  open http://localhost:8000")
    return user_id


if __name__ == "__main__":
    seed()