"""Environment compatibility with the original local NestJS setup."""
from pathlib import Path
import os
from dotenv import load_dotenv
from sqlalchemy.engine import make_url
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/"apps/api/.env")
load_dotenv(ROOT/".env")
def flag(name, fallback=False):
    value=os.getenv(name)
    if value is None or value.strip()=="": return fallback
    if value.lower() not in ("true","false","0","1"): raise RuntimeError(name+" must be true or false")
    return value.lower() in ("true","1")
def db_url():
    raw=os.environ["DATABASE_URL"]
    url=make_url(raw).set(drivername="mysql+pymysql")
    return url.update_query_dict({"charset":"utf8mb4"}).difference_update_query(["connection_limit","pool_timeout"])
