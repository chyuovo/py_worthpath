"""Single SQLAlchemy transaction boundary; never runs schema DDL at startup."""
from contextlib import contextmanager
from sqlalchemy import create_engine,event
from sqlalchemy.orm import Session
from .config import db_url
engine=create_engine(db_url(),pool_pre_ping=True,isolation_level="SERIALIZABLE",connect_args={"connect_timeout":8})
@event.listens_for(engine,"connect")
def set_timezone(connection,record):
    with connection.cursor() as cursor: cursor.execute("SET time_zone = '+00:00'")
@contextmanager
def transaction():
    with Session(engine,expire_on_commit=False) as session:
        with session.begin(): yield session
