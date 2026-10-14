"""Frozen baseline: existing WorthPath schema with no business schema changes."""

import runpy
from pathlib import Path

from sqlalchemy import inspect, text

from alembic import context, op

revision = "0001_existing_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    schema = runpy.run_path(str(Path(__file__).parents[1] / "baseline_schema.py"))[
        "SCHEMA"
    ]
    offline = context.is_offline_mode()
    present = (
        set() if offline else {n.lower() for n in inspect(connection).get_table_names()}
    )
    if present.intersection(n.lower() for n in schema):
        raise RuntimeError(
            "Baseline initialization requires an empty database; do not recreate existing tables."
        )

    def execute(sql):
        if offline:
            op.execute(text(sql.replace(":", r"\:")))
        else:
            connection.exec_driver_sql(sql)

    execute("SET FOREIGN_KEY_CHECKS=0")
    try:
        for ddl in schema.values():
            execute(ddl)
    finally:
        execute("SET FOREIGN_KEY_CHECKS=1")


def downgrade():
    raise RuntimeError(
        "Destructive downgrade disabled: explicitly restore a verified backup."
    )
