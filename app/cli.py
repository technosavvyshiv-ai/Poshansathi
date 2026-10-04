"""Flask CLI commands for the database.

Registered on the application by :func:`app.create_app` in Phase 1 so that the
schema can be created and seeded without feature routes::

    flask --app app.py init-db     # create all tables
    flask --app app.py seed-db     # insert synthetic demo data
    flask --app app.py reset-db    # drop + create (no data)
    flask --app app.py drop-db     # drop all tables
"""

from __future__ import annotations

import click
from flask import Flask
from flask.cli import with_appcontext

from app.extensions import db


@click.command("init-db")
@with_appcontext
def init_db_command() -> None:
    """Create every table defined by the models."""
    # Importing app.models registers all models on db.metadata.
    import app.models  # noqa: F401

    db.create_all()
    click.echo(f"Database initialized: {len(db.metadata.tables)} tables ready.")


@click.command("drop-db")
@with_appcontext
def drop_db_command() -> None:
    """Drop every table (destructive)."""
    import app.models  # noqa: F401

    db.drop_all()
    click.echo("Database tables dropped.")


@click.command("reset-db")
@with_appcontext
def reset_db_command() -> None:
    """Drop and recreate every table (destructive)."""
    import app.models  # noqa: F401

    db.drop_all()
    db.create_all()
    click.echo(f"Database reset: {len(db.metadata.tables)} tables ready.")


@click.command("seed-db")
@click.option("--force", is_flag=True, help="Drop and recreate all tables first.")
@with_appcontext
def seed_db_command(force: bool) -> None:
    """Populate the database with synthetic demo data."""
    from database.seed import seed_database

    result = seed_database(force=force)
    click.echo(result.summary())


@click.command("scan-alerts")
@with_appcontext
def scan_alerts_command() -> None:
    """Run the deterministic alert rules across all stored data."""
    from app.services import alert_service

    result = alert_service.evaluate_all()
    click.echo(
        "Alert scan complete: evaluated "
        f"{result['beneficiaries']} beneficiaries; "
        f"{result['active_alerts']} active alert(s)."
    )


def register_cli(app: Flask) -> None:
    """Attach the database CLI commands to ``app``."""
    app.cli.add_command(init_db_command)
    app.cli.add_command(drop_db_command)
    app.cli.add_command(reset_db_command)
    app.cli.add_command(seed_db_command)
    app.cli.add_command(scan_alerts_command)
