# 数据库事务边界：只读使用一致性快照，写入使用串行化隔离；启动不修改表结构。
"""Single SQLAlchemy transaction boundary; never runs schema DDL at startup."""

from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from .config import db_url

engine = create_engine(
    db_url(),
    pool_pre_ping=True,
    isolation_level="REPEATABLE READ",
    connect_args={"connect_timeout": 8},
)


@event.listens_for(engine, "connect")
def set_timezone(connection, record):
    with connection.cursor() as cursor:
        cursor.execute("SET time_zone = '+00:00'")


# 业务异常向外传播时自动回滚；只有整个操作成功才提交。
# 只读请求沿用 MySQL 的一致性快照，不持有 SERIALIZABLE 范围锁；业务写入才提升隔离级别。
@contextmanager
def transaction(write=False):
    with engine.connect() as connection:
        if write:
            connection = connection.execution_options(isolation_level="SERIALIZABLE")
        with Session(connection, expire_on_commit=False) as session:
            with session.begin():
                yield session
