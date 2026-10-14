"""共享图标软删除；只新增可空字段和索引，保留全部已有数据。"""

from sqlalchemy import Column, inspect
from sqlalchemy.dialects.mysql import DATETIME

from alembic import context, op

revision = "0002_icon_soft_delete"
down_revision = "0001_existing_schema"
branch_labels = None
depends_on = None


def upgrade():
    # MySQL DDL 会隐式提交；中断重试必须先核对已创建字段与索引，不能直接 stamp。
    table = "Icon"
    columns, indexes = {}, {}
    if not context.is_offline_mode():
        inspector = inspect(op.get_bind())
        table = next(
            name for name in inspector.get_table_names() if name.lower() == "icon"
        )
        columns = {c["name"]: c for c in inspector.get_columns(table)}
        indexes = {i["name"]: i for i in inspector.get_indexes(table)}
    column = columns.get("deletedAt")
    if column is not None:
        if (
            not isinstance(column["type"], DATETIME)
            or column["type"].fsp != 3
            or not column["nullable"]
            or column.get("comment") != "共享图标下架时间，UTC"
        ):
            raise RuntimeError(
                "Existing deletedAt column does not match this migration."
            )
    else:
        op.add_column(
            table,
            Column(
                "deletedAt",
                DATETIME(fsp=3),
                nullable=True,
                comment="共享图标下架时间，UTC",
            ),
        )
    index = indexes.get("Icon_shared_deletedAt_name_idx")
    if index is not None:
        if index["column_names"] != ["shared", "deletedAt", "name"] or index["unique"]:
            raise RuntimeError(
                "Existing soft-delete index does not match this migration."
            )
    else:
        op.create_index(
            "Icon_shared_deletedAt_name_idx", table, ["shared", "deletedAt", "name"]
        )


def downgrade():
    # 防止删除下架记录后使已下架图标意外重新公开。
    raise RuntimeError(
        "Destructive downgrade disabled; restore a verified backup explicitly."
    )
