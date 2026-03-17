import click
from flask.cli import with_appcontext
from app.models.database import db
from app.models.store import seed_database


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Create database tables (if not already present) and seed defaults."""
    db.create_all()
    click.echo("Initialized the database.")
    seed_database()
    click.echo("Seeded the database.")


def register_commands(app):
    app.cli.add_command(init_db_command)
