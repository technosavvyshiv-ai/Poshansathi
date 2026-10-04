"""Poshansathi - a nutrition companion.

Poshan (nutrition) + Sathi (companion).

A dependency-free Python application that helps a user track what they eat,
understand their nutritional needs, and get simple diet suggestions.

Typical usage::

    from poshansathi import database, nutrition, tracker

    database.init_db()
    conn = database.get_connection()
    user_id = tracker.create_user(conn, name="Asha", age=22, gender="female",
                                  height_cm=163, weight_kg=58,
                                  activity_level="moderate", goal="maintain")
"""

__version__ = "1.0.0"
__all__ = [
    "database",
    "models",
    "nutrition",
    "tracker",
    "suggestions",
    "reports",
]