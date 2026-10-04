#!/usr/bin/env python3
"""Poshansathi command-line interface.

An interactive menu for managing profiles, logging meals, and viewing daily
analysis and weekly reports.

Run with::

    python cli.py
"""

from __future__ import annotations

from datetime import date

from poshansathi import database, reports, tracker
from poshansathi.nutrition import (
    ACTIVITY_FACTORS, GOAL_ADJUSTMENT, profile_summary,
)
from poshansathi.suggestions import build_report

LINE = "-" * 68


def clear() -> None:
    print("\n" * 1)


def title(text: str) -> None:
    print("\n" + LINE)
    print(text.center(68))
    print(LINE)


def table(headers: list[str], rows: list[list], widths: list[int] | None = None) -> None:
    """Print a simple fixed-width table without external libraries."""
    if widths is None:
        widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) + 2
                  for i, h in enumerate(headers)]
    header = "".join(str(h).ljust(w) for h, w in zip(headers, widths))
    print(header)
    print("-" * sum(widths))
    for row in rows:
        print("".join(str(c).ljust(w) for c, w in zip(row, widths)))


def ask(prompt: str, default: str = "") -> str:
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def ask_float(prompt: str, default: float | None = None) -> float:
    while True:
        raw = input(f"{prompt}{f' [{default}]' if default is not None else ''}: ").strip()
        if not raw and default is not None:
            return default
        try:
            return float(raw)
        except ValueError:
            print("  ! Please enter a number.")


def ask_int(prompt: str, default: int | None = None) -> int:
    while True:
        raw = input(f"{prompt}{f' [{default}]' if default is not None else ''}: ").strip()
        if not raw and default is not None:
            return default
        try:
            return int(raw)
        except ValueError:
            print("  ! Please enter a whole number.")


def choose(prompt: str, options: list[str]) -> str:
    print(f"  {prompt}")
    for i, opt in enumerate(options, 1):
        print(f"    {i}. {opt}")
    while True:
        raw = input("  choice: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("  ! Invalid choice.")


# --------------------------------------------------------------------------
# Screens
# --------------------------------------------------------------------------
def select_user(conn) -> int | None:
    users = tracker.list_users(conn)
    if not users:
        print("\nNo profiles yet. Let's create one.")
        return create_user(conn)
    title("Select a profile")
    table(["#", "Name", "Goal", "Weight"], [
        [u.id, u.name, u.goal, f"{u.weight_kg:.0f} kg"] for u in users
    ])
    print("   0. Create a new profile")
    choice = ask_int("  Select profile")
    if choice == 0:
        return create_user(conn)
    if any(u.id == choice for u in users):
        return choice
    print("  ! No such profile.")
    return None


def create_user(conn) -> int:
    title("Create a new profile")
    name = ask("Name")
    age = ask_int("Age", 25)
    gender = choose("Gender", ["male", "female", "other"])
    height = ask_float("Height (cm)", 165)
    weight = ask_float("Weight (kg)", 60)
    activity = choose("Activity level", list(ACTIVITY_FACTORS.keys()))
    goal = choose(
        "Goal",
        [f"{g}  ({'+' if v >= 0 else ''}{v:.0f} kcal/day)"
         for g, v in GOAL_ADJUSTMENT.items()],
    )
    goal_key = goal.split()[0]
    user_id = tracker.create_user(conn, name, age, gender, height, weight,
                                  activity, goal_key)
    print(f"\n  Profile created (#{user_id}, {name}).")
    return user_id


def show_profile(conn, user_id: int) -> None:
    user = tracker.get_user(conn, user_id)
    summary = profile_summary(user)
    title(f"Profile: {user.name}")
    print(f"  Age {user.age} | {user.gender} | {user.height_cm:.0f} cm | "
          f"{user.weight_kg:.0f} kg | {user.activity_level} | goal: {user.goal}")
    lo, hi = summary["healthy_weight_range"]
    print(f"\n  BMI: {summary['bmi']}  ({summary['bmi_category']})")
    print(f"  Healthy weight range: {lo}-{hi} kg")
    print(f"  BMR: {summary['bmr']:.0f} kcal/day")
    print(f"  TDEE: {summary['tdee']:.0f} kcal/day")
    print(f"  Daily target: {summary['target_calories']:.0f} kcal")
    m = summary["macros"]
    print(f"  Macros: protein {m['protein_g']}g | carbs {m['carbs_g']}g | "
          f"fat {m['fat_g']}g")


def browse_foods(conn) -> None:
    categories = tracker.list_categories(conn)
    cat = choose("Filter by category", ["All"] + categories)
    foods = tracker.list_foods(conn, None if cat == "All" else cat)
    title("Food database")
    table(
        ["ID", "Name", "Serving", "kcal", "P", "C", "F"],
        [[f.id, f.name, f.serving_desc, f"{f.calories:.0f}",
          f"{f.protein_g:.0f}", f"{f.carbs_g:.0f}", f"{f.fat_g:.0f}"]
         for f in foods],
    )
    print(f"\n  {len(foods)} items.  (P=protein g, C=carbs g, F=fat g)")


def log_meal(conn, user_id: int) -> None:
    meal = choose("Meal", list(tracker.MEAL_TYPES))
    term = ask("Search food (name contains)")
    matches = tracker.search_foods(conn, term) if term else tracker.list_foods(conn)
    if not matches:
        print("  ! No matching foods. Try 'browse' from the menu to see names.")
        return
    title("Choose a food")
    table(["#", "Name", "Serving", "kcal"],
          [[i, f.name, f.serving_desc, f"{f.calories:.0f}"]
           for i, f in enumerate(matches, 1)])
    idx = ask_int("  # of food")
    if not (1 <= idx <= len(matches)):
        print("  ! Invalid selection.")
        return
    qty = ask_float("  Quantity (servings)", 1.0)
    day = ask("  Date (YYYY-MM-DD)", date.today().isoformat())
    tracker.log_meal(conn, user_id, day, meal, matches[idx - 1].id, qty)
    food = matches[idx - 1]
    print(f"  Logged {qty:g} x {food.name} ({food.calories * qty:.0f} kcal) "
          f"for {meal} on {day}.")


def show_day(conn, user_id: int) -> None:
    day = ask("Date (YYYY-MM-DD)", date.today().isoformat())
    entries = tracker.get_entries(conn, user_id, day)
    title(f"Meals for {day}")
    if not entries:
        print("  Nothing logged yet.")
        return
    table(["ID", "Meal", "Food", "Qty", "kcal"],
          [[e["id"], e["meal_type"], e["food_name"], f"{e['quantity']:g}",
            f"{e['total_calories']:.0f}"] for e in entries])
    totals = tracker.daily_totals(conn, user_id, day)
    t = totals.as_dict()
    print(f"\n  Calories {t['calories']:.0f} | protein {t['protein_g']}g | "
          f"carbs {t['carbs_g']}g | fat {t['fat_g']}g | fibre {t['fiber_g']}g")


def daily_analysis(conn, user_id: int) -> None:
    user = tracker.get_user(conn, user_id)
    day = ask("Date (YYYY-MM-DD)", date.today().isoformat())
    totals = tracker.daily_totals(conn, user_id, day)
    report = build_report(conn, user, totals)

    title(f"Analysis for {day}")
    cal = report["calories"]
    print(f"  Calories: {cal['consumed']:.0f} / {cal['target']:.0f} kcal "
          f"({cal['percent']:.0f}%)")
    print(f"  {cal['message']}\n")

    print("  Macros vs target")
    for macro, info in report["macros"].items():
        bar = "#" * min(30, int(info["percent"] / 4))
        print(f"    {macro:<8} {info['value']:>6}g / {info['target']:>6}g "
              f"[{bar:<30}] {info['percent']:.0f}%")

    print("\n  Nutrient gaps")
    if not report["gaps"]:
        print("    All tracked nutrients met. Great job!")
    for gap in report["gaps"]:
        flag = " (LOW)" if gap["critical"] else ""
        print(f"    {gap['nutrient']:<14} {gap['value']:>7} / {gap['target']:<7} "
              f"{gap['percent']:>3.0f}%{flag}")

    if report["recommendations"]:
        print("\n  Try adding:")
        for nutrient, foods in report["recommendations"].items():
            names = ", ".join(f["food"].name for f in foods)
            print(f"    for {nutrient}: {names}")

    if report["tip"]:
        print(f"\n  Tip: {report['tip']}")


def weekly_report(conn, user_id: int) -> None:
    user = tracker.get_user(conn, user_id)
    summary = reports.weekly_summary(conn, user_id)
    title(f"Weekly report: {summary['start']} to {summary['end']}")
    if not summary["days"]:
        print("  No meals logged this week.")
        return
    table(["Date", "Calories", "Protein", "Carbs", "Fat"],
          [[d["date"], f"{d['calories']:.0f}", f"{d['protein_g']:.0f}",
            f"{d['carbs_g']:.0f}", f"{d['fat_g']:.0f}"]
           for d in summary["days"]])
    avg = summary["averages"]
    print(f"\n  Logged {summary['logged_days']} day(s).  "
          f"Average: {avg['calories']:.0f} kcal | "
          f"P {avg['protein_g']:.0f}g | C {avg['carbs_g']:.0f}g | "
          f"F {avg['fat_g']:.0f}g")
    target = profile_summary(user)["target_calories"]
    print(f"  Target: {target:.0f} kcal/day")


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------
MENU = [
    ("Show profile & targets", "profile"),
    ("Browse food database", "browse"),
    ("Log a meal", "log"),
    ("Show a day's meals", "day"),
    ("Daily analysis & suggestions", "analysis"),
    ("Weekly report", "week"),
    ("Switch / create profile", "switch"),
    ("Quit", "quit"),
]


def main() -> None:
    conn = database.init_db()
    title("Poshansathi - Nutrition Companion")
    user_id = select_user(conn)

    while True:
        title("Main menu")
        for i, (label, _) in enumerate(MENU, 1):
            print(f"  {i}. {label}")
        raw = input("\n  Select: ").strip()
        action = MENU[int(raw) - 1][1] if raw.isdigit() and 1 <= int(raw) <= len(MENU) else None

        if action == "quit" or (raw.lower() in ("q", "quit", "exit")):
            print("\n  Stay healthy! Goodbye.\n")
            break
        if action == "profile":
            show_profile(conn, user_id)
        elif action == "browse":
            browse_foods(conn)
        elif action == "log":
            log_meal(conn, user_id)
        elif action == "day":
            show_day(conn, user_id)
        elif action == "analysis":
            daily_analysis(conn, user_id)
        elif action == "week":
            weekly_report(conn, user_id)
        elif action == "switch":
            new_id = select_user(conn)
            if new_id:
                user_id = new_id
        else:
            print("  ! Invalid selection.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\n  Goodbye!\n")