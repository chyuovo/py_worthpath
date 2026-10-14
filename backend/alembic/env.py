# Alembic 管理当前数据库版本；备份和结构检查由 scripts/database.py 提供。
from sqlalchemy import (
    Column,
    ForeignKeyConstraint,
    Index,
    MetaData,
    Table,
    UniqueConstraint,
)

from alembic import context
from app.database import engine
from app.models import Base


def metadata_for(connection):
    # Windows MySQL 的 lower_case_table_names=1 会返回小写表名；规范化比较避免误生成删表重建。
    if connection.exec_driver_sql("SELECT @@lower_case_table_names").scalar() == 0:
        return Base.metadata
    result = MetaData()
    for table in Base.metadata.tables.values():
        columns = [
            Column(
                c.name,
                c.type.copy(),
                primary_key=c.primary_key,
                nullable=c.nullable,
                server_default=c.server_default,
                comment=c.comment,
            )
            for c in table.columns
        ]
        target = Table(table.name.lower(), result, *columns, comment=table.comment)
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint):
                target.append_constraint(
                    UniqueConstraint(
                        *[c.name for c in constraint.columns], name=constraint.name
                    )
                )
        for index in table.indexes:
            Index(
                index.name,
                *[target.c[c.name] for c in index.columns],
                unique=index.unique,
            )
    for table in Base.metadata.tables.values():
        target = result.tables[table.name.lower()]
        for constraint in table.foreign_key_constraints:
            target.append_constraint(
                ForeignKeyConstraint(
                    [e.parent.name for e in constraint.elements],
                    [
                        e.column.table.name.lower() + "." + e.column.name
                        for e in constraint.elements
                    ],
                    name=constraint.name,
                    ondelete=constraint.ondelete,
                    onupdate=constraint.onupdate,
                )
            )
    return result


# 比较真实默认值；金额默认值按 Decimal 比较，字符串大小写不能被忽略。
def compare_defaults(
    context,
    inspected_column,
    metadata_column,
    inspected_default,
    metadata_default,
    rendered_default,
):
    if inspected_default is None or rendered_default is None:
        return inspected_default is not None or rendered_default is not None
    left = str(inspected_default).strip().strip("'").strip('"')
    right = str(rendered_default).strip().strip("'").strip('"')
    from sqlalchemy import Boolean, Integer, Numeric

    if isinstance(metadata_column.type, (Numeric, Integer, Boolean)):
        from decimal import Decimal, InvalidOperation

        try:
            return Decimal(left) != Decimal(right)
        except InvalidOperation:
            pass
    if "current_timestamp" in left.lower() and "current_timestamp" in right.lower():
        return left.lower().replace(" ", "") != right.lower().replace(" ", "")
    return left != right


def include_object(object, name, type, reflected, compare_to):
    # 只比较当前模型管理的表，不自动删除其他表。删表须人工审查并明确执行。
    return not (type == "table" and reflected and compare_to is None)


if context.is_offline_mode():
    context.configure(
        url=engine.url,
        target_metadata=Base.metadata,
        literal_binds=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=metadata_for(connection),
            compare_type=True,
            compare_server_default=compare_defaults,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()
