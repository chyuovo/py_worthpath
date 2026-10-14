# 共享规则：金额只使用 Decimal；数据库时间为 UTC，业务展示时间为 UTC+8。
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal, getcontext, ROUND_HALF_UP, DefaultContext
import hashlib
from fastapi import HTTPException
from sqlalchemy import select

DefaultContext.prec = 50
DefaultContext.rounding = ROUND_HALF_UP
getcontext().prec = 50
getcontext().rounding = ROUND_HALF_UP
TZ = timezone(timedelta(hours=8))


def now():
    # 与 JavaScript Date 和 MySQL DATETIME(3) 一致，创建时即截到毫秒，保证幂等重试返回完全相同的时间。
    value = datetime.now(timezone.utc).replace(tzinfo=None)
    return value.replace(microsecond=value.microsecond // 1000 * 1000)


def today():
    return datetime.now(TZ).date().isoformat()


def iso(v):
    if isinstance(v, datetime):
        return (
            v.replace(tzinfo=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
    if isinstance(v, date):
        return v.isoformat() + "T00:00:00.000Z"
    return v


def business_time(v):
    return (v + timedelta(hours=8)).isoformat(timespec="minutes")


def business_day(v):
    return business_time(v)[:10]


# 用户输入为北京时间，存入 MySQL 前转换成不带时区的 UTC 时间。
def business_date(value):
    s = value + "T00:00" if len(value) == 10 else value
    return (
        datetime.fromisoformat(s)
        .replace(tzinfo=TZ)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def dec(v):
    return Decimal(str(v))


def fixed(v, n=None):
    d = dec(v)
    if d.is_zero():
        d = abs(d)
    if n is not None:
        return format(d.quantize(Decimal(1).scaleb(-n)), "f")
    s = format(d, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


# Prisma Decimal.toString 使用与 Decimal.js 相同的科学计数阈值；计算结果仍用 fixed 保持原公式。
def decimal_string(value):
    d = dec(value)
    if d.is_zero():
        return "0"
    exponent = d.adjusted()
    if exponent <= -7 or exponent >= 21:
        return (
            fixed(d.scaleb(-exponent))
            + "e"
            + ("+" if exponent >= 0 else "")
            + str(exponent)
        )
    return fixed(d)


def digest(v):
    return hashlib.sha256(v.encode()).hexdigest()


def fail(message, status=400):
    raise HTTPException(status_code=status, detail=message)


def row(v):
    return {
        c.name: getattr(v, "metadata_" if c.name == "metadata" else c.name)
        for c in v.__table__.columns
    }


def serializable(v):
    if isinstance(v, Decimal):
        return decimal_string(v)
    if isinstance(v, (date, datetime)):
        return iso(v)
    if isinstance(v, dict):
        return {k: serializable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [serializable(x) for x in v]
    if hasattr(v, "__table__"):
        return serializable(row(v))
    return v


def one(s, model, **where):
    return s.scalar(select(model).filter_by(**where))


DEFAULT_CARDS = [
    "assets",
    "liabilities",
    "net",
    "trend",
    "composition",
    "recent",
    "attribution",
]
PAIRED = [
    "transfer_out",
    "transfer_in",
    "loan_borrow",
    "loan_lend",
    "loan_collect",
    "loan_repay",
]
CURRENCIES = ["CNY", "USD", "HKD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "SGD"]
