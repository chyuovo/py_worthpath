from datetime import datetime,date,timezone,timedelta
from decimal import Decimal,getcontext,ROUND_HALF_UP
import hashlib
from fastapi import HTTPException
from sqlalchemy import select
getcontext().prec=50
getcontext().rounding=ROUND_HALF_UP
TZ=timezone(timedelta(hours=8))
def now():return datetime.now(timezone.utc).replace(tzinfo=None)
def today():return datetime.now(TZ).date().isoformat()
def iso(v):
    if isinstance(v,datetime):return v.replace(tzinfo=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")
    if isinstance(v,date):return v.isoformat()+"T00:00:00.000Z"
    return v
def business_time(v):return (v+timedelta(hours=8)).isoformat(timespec="minutes")
def business_day(v):return business_time(v)[:10]
def business_date(value):
    s=value+"T00:00" if len(value)==10 else value
    return datetime.fromisoformat(s).replace(tzinfo=TZ).astimezone(timezone.utc).replace(tzinfo=None)
def dec(v):return Decimal(str(v))
def fixed(v,n=None):
    d=dec(v)
    if n is not None:return format(d.quantize(Decimal(1).scaleb(-n)),"f")
    s=format(d,"f")
    return s.rstrip("0").rstrip(".") if "." in s else s
def digest(v):return hashlib.sha256(v.encode()).hexdigest()
def fail(message,status=400):raise HTTPException(status_code=status,detail=message)
def row(v):return {c.name:getattr(v,"metadata_" if c.name=="metadata" else c.name) for c in v.__table__.columns}
def serializable(v):
    if isinstance(v,Decimal):return fixed(v)
    if isinstance(v,(date,datetime)):return iso(v)
    if isinstance(v,dict):return {k:serializable(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [serializable(x) for x in v]
    if hasattr(v,"__table__"):return serializable(row(v))
    return v
def one(s,model,**where):return s.scalar(select(model).filter_by(**where))
DEFAULT_CARDS=["assets","liabilities","net","trend","composition","recent","attribution"]
PAIRED=["transfer_out","transfer_in","loan_borrow","loan_lend","loan_collect","loan_repay"]
CURRENCIES=["CNY","USD","HKD","EUR","GBP","JPY","AUD","CAD","CHF","SGD"]
