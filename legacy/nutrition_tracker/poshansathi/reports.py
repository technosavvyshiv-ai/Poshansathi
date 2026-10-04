"""Weekly and multi-day summaries."""

from __future__ import annotations

import sqlite3
import statistics
from datetime import date

from . import tracker


def weekly_summary(conn: sqlite3.Connection, user_id: int,
                   reference: date | None = None) -> dict:
    """Summarise the days logged in the week containing ``reference``."""
    start, end = tracker.week_bounds(reference)
    days = tracker.entries_between(conn, user_id, start, end)

    if not days:
        return {"start": start, "end": end, "days": [], "logged_days": 0,
                "averages": {}, "totals": {}}

    def avg(key: str) -> float:
        return round(statistics.mean(d[key] for d in days), 1)

    totals = {
        key: round(sum(d[key] for d in days), 1)
        for key in ("calories", "protein_g", "carbs_g", "fat_g")
    }
    return {
        "start": start,
        "end": end,
        "days": days,
        "logged_days": len(days),
        "averages": {
            "calories": avg("calories"),
            "protein_g": avg("protein_g"),
            "carbs_g": avg("carbs_g"),
            "fat_g": avg("fat_g"),
        },
        "totals": totals,
    }