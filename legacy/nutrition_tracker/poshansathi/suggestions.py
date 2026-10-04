"""Rule-based diet suggestions.

The engine compares a day's :class:`~poshansathi.models.NutritionTotals`
against reference targets, then recommends foods that help close the gap.
It is intentionally simple and transparent - every suggestion can be
explained by a number.
"""

from __future__ import annotations

import sqlite3

from .models import NutritionTotals
from .nutrition import RDA, macro_targets
from . import tracker

# A gap below this fraction of the target is considered "critically low".
LOW_THRESHOLD = 0.60

# Which nutrient each food column maps to, used to rank recommendations.
NUTRIENT_COLUMNS = {
    "fiber_g": "fiber_g",
    "iron_mg": "iron_mg",
    "calcium_mg": "calcium_mg",
    "vitamin_c_mg": "vitamin_c_mg",
}

GOAL_TIPS = {
    "lose": "Prioritise protein and fibre to stay full while in a deficit; "
            "avoid sugary drinks and fried snacks.",
    "maintain": "Keep meals balanced - half the plate vegetables, a quarter "
                "protein, a quarter whole grains.",
    "gain": "Add calorie-dense whole foods (nuts, ghee, dairy) and eat every "
            "3-4 hours to support a surplus.",
}


def nutrient_gaps(totals: NutritionTotals) -> list[dict]:
    """Return a list of nutrients that are below their RDA.

    Each item has ``nutrient``, ``value``, ``target`` and ``percent``.
    """
    gaps = []
    for nutrient, target in RDA.items():
        value = getattr(totals, nutrient, 0.0)
        percent = (value / target * 100.0) if target else 100.0
        if percent < 100.0:
            gaps.append({
                "nutrient": nutrient,
                "value": round(value, 1),
                "target": target,
                "percent": round(percent, 0),
                "critical": percent < LOW_THRESHOLD * 100.0,
            })
    return sorted(gaps, key=lambda g: g["percent"])


def suggest_foods(conn: sqlite3.Connection, gaps: list[dict],
                  limit: int = 3, vegetarian_only: bool = False) -> dict:
    """Recommend the top foods for each nutrient gap.

    Returns ``{nutrient: [{"food": Food, "amount": ...}, ...]}``.
    """
    recommendations: dict[str, list] = {}
    for gap in gaps:
        column = NUTRIENT_COLUMNS.get(gap["nutrient"])
        if not column:
            continue
        query = f"""
            SELECT * FROM foods
            WHERE {column} > 0
            {('AND is_veg = 1' if vegetarian_only else '')}
            ORDER BY {column} DESC
            LIMIT ?
        """
        rows = conn.execute(query, (limit,)).fetchall()
        recommendations[gap["nutrient"]] = [
            {"food": tracker._row_to_food(r), "amount": r[column]}
            for r in rows
        ]
    return recommendations


def calorie_advice(totals: NutritionTotals, target_calories: float) -> dict:
    """Compare consumed calories with the target and describe the difference."""
    consumed = totals.calories
    remaining = target_calories - consumed
    percent = (consumed / target_calories * 100.0) if target_calories else 0.0
    if percent < 80:
        status = "under"
        message = f"You are {abs(remaining):.0f} kcal under target. " \
                  "Consider a protein-rich snack."
    elif percent <= 110:
        status = "on_track"
        message = "Calories are on target. Well done!"
    else:
        status = "over"
        message = f"You are {remaining * -1:.0f} kcal over target. " \
                  "Watch fried and sugary items."
    return {
        "consumed": round(consumed, 0),
        "target": round(target_calories, 0),
        "remaining": round(remaining, 0),
        "percent": round(percent, 0),
        "status": status,
        "message": message,
    }


def build_report(conn: sqlite3.Connection, user, totals: NutritionTotals) -> dict:
    """Bundle everything a UI needs to show a daily analysis screen."""
    from .nutrition import profile_summary  # local import avoids cycles

    profile = profile_summary(user)
    targets = profile["macros"]
    macro_status = {}
    for macro, key in (("protein", "protein_g"), ("carbs", "carbs_g"),
                       ("fat", "fat_g")):
        target = targets[key]
        value = getattr(totals, key, 0.0)
        macro_status[macro] = {
            "value": round(value, 1),
            "target": target,
            "percent": round(value / target * 100.0, 0) if target else 0.0,
        }
    gaps = nutrient_gaps(totals)
    return {
        "profile": profile,
        "totals": totals.as_dict(),
        "calories": calorie_advice(totals, profile["target_calories"]),
        "macros": macro_status,
        "gaps": gaps,
        "recommendations": suggest_foods(conn, gaps),
        "tip": GOAL_TIPS.get(user.goal, ""),
    }