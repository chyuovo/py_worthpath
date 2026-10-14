# Alembic 是唯一结构执行入口；接管检查和备份由 scripts/database.py 完成。
from alembic import context
from sqlalchemy import MetaData,Table,Column,ForeignKeyConstraint,UniqueConstraint,Index,text
from app.database import engine
from app.models import Base
def metadata_for(connection):
    # Windows MySQL 的 lower_case_table_names=1 会返回小写表名；规范化比较避免误生成删表重建。
    if connection.exec_driver_sql("SELECT @@lower_case_table_names").scalar()==0:return Base.metadata
    result=MetaData()
    for table in Base.metadata.tables.values():
        columns=[Column(c.name,c.type.copy(),primary_key=c.primary_key,nullable=c.nullable,server_default=c.server_default,comment=c.comment) for c in table.columns]
        target=Table(table.name.lower(),result,*columns,comment=table.comment)
        for constraint in table.constraints:
            if isinstance(constraint,UniqueConstraint):target.append_constraint(UniqueConstraint(*[c.name for c in constraint.columns],name=constraint.name))
        for index in table.indexes:Index(index.name,*[target.c[c.name] for c in index.columns],unique=index.unique)
    for table in Base.metadata.tables.values():
        target=result.tables[table.name.lower()]
        for constraint in table.foreign_key_constraints:
            target.append_constraint(ForeignKeyConstraint([e.parent.name for e in constraint.elements],[e.column.table.name.lower()+"."+e.column.name for e in constraint.elements],name=constraint.name,ondelete=constraint.ondelete,onupdate=constraint.onupdate))
    return result
def include_object(object,name,type,reflected,compare_to):
    # 原 Prisma 历史仅保留审计用途，不能被 Alembic 自动生成为删除目标。
    return not (type=="table" and name.lower()=="_prisma_migrations")
if context.is_offline_mode():
    context.configure(url=engine.url,target_metadata=Base.metadata,literal_binds=True,include_object=include_object)
    with context.begin_transaction():context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=metadata_for(connection),compare_type=True,include_object=include_object)
        with context.begin_transaction():context.run_migrations()
