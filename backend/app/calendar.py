# 收支日历：由余额变化估算收支，排除初始余额、内部转账与借贷本金。
import calendar as cal, re
from sqlalchemy import select
from .common import *
from .models import *
from .queries import current_positions, rates, rate_history
from .calculation import rate_at
from .schemas import check_date


def changes(s, r, start, end, details=False):
    ps = current_positions(s, r, kind="account", all_history=True, start=start, end=end)
    base = s.get(User, r.userId).baseCurrency
    rs = rate_history(s, r, [p["currency"] for p in ps], base, start, end)
    out = []
    for p in ps:
        before = None
        for v in p["revisions"]:
            day = business_day(v["effectiveDate"])
            amount = dec(v["amount"])
            delta = (
                amount - before
                if before is not None
                else amount
                if v["reason"] == "scheduled_expense"
                else dec(0)
            )
            before = amount
            if not start <= day <= end or v["reason"] not in (
                "balance",
                "correction",
                "scheduled_expense",
            ):
                continue
            if p["side"] == "liability":
                delta = -delta
            if delta == 0:
                continue
            fx = rate_at(rs, p["currency"], base, day)
            out.append(
                {
                    "id": v["id"],
                    "name": p["name"],
                    "currency": p["currency"],
                    "date": day,
                    "notes": v["notes"] if details else "",
                    "amount": fixed(abs(delta)),
                    "direction": "expense" if delta < 0 else "income",
                    "converted": fixed(abs(delta) * fx["value"]) if fx else None,
                    "_sort": (v["effectiveDate"], v["sequence"]),
                }
            )
    out.sort(key=lambda v: v.pop("_sort"))
    return base, out


def dispatch(s, r, request, response, body):
    path = request.scope["route"].path
    q = request.query_params
    if path == "/api/calendar/day":
        day = q.get("date", today())
        check_date(day)
        base, items = changes(s, r, day, day, True)
        return dict(date=day, baseCurrency=base, revealed=r.revealed, items=items)
    if path == "/api/calendar":
        month = q.get("month", today()[:7])
        if (
            not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month)
            or not "1900-01" <= month <= today()[:7]
        ):
            fail("月份无效")
        year, m = map(int, month.split("-"))
        days = cal.monthrange(year, m)[1]
        start = month + "-01"
        end = min(month + "-" + str(days), today())
        base, items = changes(s, r, start, end)
        output = [
            dict(
                date=month + "-" + str(i).zfill(2),
                income=dec(0),
                expense=dec(0),
                complete=True,
            )
            for i in range(1, days + 1)
        ]
        for v in items:
            day = output[int(v["date"][-2:]) - 1]
            if v["converted"] is None:
                day["complete"] = False
            else:
                day[v["direction"]] += dec(v["converted"])
        for v in output:
            v["income"] = fixed(v["income"], 2)
            v["expense"] = fixed(v["expense"], 2)
        return dict(month=month, baseCurrency=base, revealed=r.revealed, items=output)
    return NotImplemented
