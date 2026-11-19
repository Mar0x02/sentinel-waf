"""Lightweight additive-column auto-migration.

This project has no Alembic (see CLAUDE.md). On a brand-new install there is
nothing to migrate - create_all() creates every table fully-formed, so
run_schema_upgrades() does zero work (it bails out before even listing
columns). On an existing install being upgraded to a version that added a
column to a table that already exists, this adds the missing column(s)
automatically instead of requiring a manual `ALTER TABLE`.

Only handles the one shape this project has ever actually needed: a new
nullable-or-defaulted column on an existing table. Renaming/dropping a
column, or any real data migration, is out of scope - reach for Alembic if
that's ever actually needed instead of growing this file to cover it.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db import Base


def run_schema_upgrades(engine: Engine) -> None:
    inspector = inspect(engine)
    pre_existing_tables = set(inspector.get_table_names())
    if not pre_existing_tables:
        return

    for table in Base.metadata.sorted_tables:
        if table.name not in pre_existing_tables:
            continue  # brand-new table - create_all() will create it fully-formed
        existing_columns = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in existing_columns:
                _add_column(engine, table, column)


def _add_column(engine: Engine, table, column) -> None:
    # A SchemaType (e.g. Enum, which SQLAlchemy backs with a real Postgres
    # `CREATE TYPE ... AS ENUM` rather than a plain VARCHAR) needs its type
    # created before a column of that type can be added.
    if hasattr(column.type, "create"):
        column.type.create(bind=engine, checkfirst=True)

    coltype = column.type.compile(dialect=engine.dialect)
    ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {coltype}"
    if column.default is not None and column.default.is_scalar:
        literal = column.type.literal_processor(engine.dialect)(column.default.arg)
        ddl += f" DEFAULT {literal}"
    elif not column.nullable:
        raise RuntimeError(
            f"cannot auto-add NOT NULL column {table.name}.{column.name}: "
            "no scalar default to backfill existing rows with"
        )
    if not column.nullable:
        ddl += " NOT NULL"

    with engine.begin() as conn:
        conn.execute(text(ddl))
