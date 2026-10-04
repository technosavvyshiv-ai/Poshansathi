"""Flask extension instances.

Extensions are created here (without an app) and bound to the application
inside the factory via ``init_app``.  This keeps the application modular and
avoids circular imports.

Phase 2 authentication is built on Flask's signed sessions (see
``app/utils/helpers.py`` and ``app/routes/auth.py``), so no Flask-Login
extension is required.
"""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

# Database ORM.  Models live in ``app/models`` and are imported in the factory.
db = SQLAlchemy()
