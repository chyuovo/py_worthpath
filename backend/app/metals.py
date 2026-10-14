# 贵金属估价：按原重量、纯度和报价计算，保留历史，失败时不覆盖已有估值。
import json, httpx
from sqlalchemy import select
from .common import *
from .models import *
from .queries import own, latest
from .schemas import money, check_date
from .settings import PUBLIC_RATES

STATUS = {}


def status(user):
    return STATUS.get(
        user, dict(state="idle", message="尚未尝试更新", attemptedAt=None)
    )


def config(body, holding=False):
    allowed = {"metalType", "metalGrams", "metalCostPerGram", "autoValuation"} | (
        {"name", "currency", "notes", "hidden", "included", "date"}
        if holding
        else set()
    )
    if (
        not isinstance(body, dict)
        or set(body) - allowed
        or not {"metalType", "metalGrams", "autoValuation"}.issubset(body)
    ):
        fail("贵金属参数无效")
    if (
        body["metalType"] not in ("gold", "silver")
        or type(body["autoValuation"]) is not bool
    ):
        fail("贵金属参数无效")
    money(body["metalGrams"], False, True)
    if body.get("metalCostPerGram") is not None:
        money(body["metalCostPerGram"], False, True, 12)
    if holding:
        if (
            not isinstance(body.get("name"), str)
            or not 1 <= len(body["name"].strip()) <= 100
            or body.get("currency") not in CURRENCIES
        ):
            fail("贵金属参数无效")
        check_date(body.get("date"))
        if (
            not isinstance(body.get("notes", ""), str)
            or len(body.get("notes", "")) > 2000
        ):
            fail("备注无效")
        if any(type(body[k]) is not bool for k in ("hidden", "included") if k in body):
            fail("贵金属参数无效")
    return dict(body)


def value(s, r, id, force=False, when=None):
    p = own(s, r, id, True)
    if p.kind != "asset" or p.category != "gold" or p.archived:
        fail("贵金属资产不存在或已归档", 404)
    if not p.metalType or not p.metalGrams:
        fail("请先设置贵金属品种和重量")
    day = business_day(when) if when else today()
    quote = s.scalar(
        select(MetalPrice)
        .where(
            MetalPrice.userId == r.userId,
            MetalPrice.metalType == p.metalType,
            MetalPrice.currency == p.currency,
            MetalPrice.date <= date.fromisoformat(day),
        )
        .order_by(MetalPrice.date.desc())
        .limit(1)
    )
    if not quote:
        fail("缺少该币种的贵金属价格，请刷新报价后重试")
    amount = dec(p.metalGrams) * dec(p.metalPurity) * dec(quote.price)
    if amount >= dec("10000000000000000"):
        fail("估价超出支持范围")
    amount = dec(fixed(amount, 8))
    last = latest(s, id)
    if last and (
        dec(last.amount) == amount
        or (not force and business_day(last.effectiveDate) > quote.date.isoformat())
    ):
        return {"amount": fixed(amount, 8), "changed": False}
    effective = when or business_date(business_time(now()))
    if last and last.effectiveDate > effective:
        fail("估价时间不能早于最新余额")
    memo = f"贵金属估价：{fixed(p.metalGrams)} 克 × 纯度 {fixed(p.metalPurity)} × {fixed(quote.price)} {p.currency}/克；报价 {quote.date.isoformat()}（{quote.source}）"
    s.add(
        Revision(
            positionId=id,
            amount=amount,
            effectiveDate=effective,
            reason="valuation",
            notes=memo,
        )
    )
    return {"amount": fixed(amount, 8), "changed": True}


def refresh(s, r):
    ps = s.scalars(
        select(Position).where(
            Position.userId == r.userId,
            Position.kind == "asset",
            Position.category == "gold",
            Position.archived.is_(False),
            Position.metalType.is_not(None),
        )
    ).all()
    if not ps:
        message = "当前没有已设置重量的贵金属资产"
        STATUS[r.userId] = dict(state="ok", message=message, attemptedAt=iso(now()))
        return {"message": message}
    try:
        urls = [
            "https://api.gold-api.com/price/XAU",
            "https://api.gold-api.com/price/XAG",
            PUBLIC_RATES,
        ]
        raw = []
        for url in urls:
            res = httpx.get(url, timeout=12)
            res.raise_for_status()
            raw.append(json.loads(res.text, parse_float=str, parse_int=str))
        quotes = {"gold": raw[0], "silver": raw[1]}
        fx = {v["quote"]: v for v in raw[2]}
        for metal, q in quotes.items():
            if q.get("currency") != "USD" or q.get("symbol") != (
                "XAU" if metal == "gold" else "XAG"
            ):
                raise ValueError()
            money(q["price"], False, True, 12)
            when = datetime.fromisoformat(
                q["updatedAt"].replace("Z", "+00:00")
            ).replace(tzinfo=None)
            if not now() - timedelta(days=14) <= when <= now() + timedelta(minutes=1):
                raise ValueError()
        s.scalar(select(User).where(User.id == r.userId).with_for_update())
        for p in ps:
            q = quotes[p.metalType]
            when = datetime.fromisoformat(
                q["updatedAt"].replace("Z", "+00:00")
            ).replace(tzinfo=None)
            conversion = fx.get(p.currency) if p.currency != "USD" else None
            if p.currency != "USD" and not conversion:
                raise ValueError()
            if conversion and not (
                date.fromisoformat(today()) - timedelta(days=14)
                <= date.fromisoformat(conversion["date"])
                <= date.fromisoformat(today())
            ):
                raise ValueError()
            price = fixed(
                dec(q["price"])
                / dec("31.1034768")
                * dec(conversion["rate"] if conversion else 1),
                12,
            )
            money(price, False, True, 12)
            key = dict(
                userId=r.userId,
                metalType=p.metalType,
                currency=p.currency,
                date=date.fromisoformat(business_day(when)),
            )
            old = one(s, MetalPrice, **key)
            if not old:
                s.add(MetalPrice(**key, price=price, source="goldapi", quotedAt=when))
                s.flush()
            elif old.source != "manual":
                old.price = price
                old.source = "goldapi"
                old.quotedAt = when
            if p.autoValuation:
                from .auth import Context

                value(s, Context(r.userId, r.sessionId, True), p.id)
        message = "贵金属参考价已更新，已开启的自动估价已记入历史"
        STATUS[r.userId] = dict(state="ok", message=message, attemptedAt=iso(now()))
        return {"message": message}
    except Exception:
        STATUS[r.userId] = dict(
            state="error",
            message="贵金属价格更新失败，已有价格与估值已保留，请稍后重试",
            attemptedAt=iso(now()),
        )
        fail("贵金属价格更新失败，已有价格与估值已保留，请稍后重试", 502)


def dispatch(s, r, request, response, body):
    path = request.scope["route"].path
    if path == "/api/metals":
        if not r.agent:
            from .quotes import daily

            daily(r.userId, "metals")
        return {
            "status": status(r.userId),
            "prices": list(
                s.scalars(
                    select(MetalPrice)
                    .where(MetalPrice.userId == r.userId)
                    .order_by(MetalPrice.date.desc())
                    .limit(100)
                )
            ),
        }
    if path == "/api/metals/refresh":
        return refresh(s, r)
    if path == "/api/metals/holdings":
        v = config(body, True)
        when = business_date(v.pop("date"))
        v["name"] = v["name"].strip()
        p = Position(
            userId=r.userId,
            kind="asset",
            side="asset",
            category="gold",
            notes="",
            createdAt=when,
            **{k: x for k, x in v.items() if k != "notes"},
        )
        p.notes = v.get("notes", "")
        s.add(p)
        s.flush()
        quote = s.scalar(
            select(MetalPrice.id)
            .where(
                MetalPrice.userId == r.userId,
                MetalPrice.metalType == p.metalType,
                MetalPrice.currency == p.currency,
                MetalPrice.date <= date.fromisoformat(business_day(when)),
            )
            .limit(1)
        )
        if quote:
            from .auth import Context

            value(s, Context(r.userId, r.sessionId, True), p.id, True, when)
        from .quotes import invalidate

        invalidate(r.userId, "metals")
        return {"id": p.id, "valuationAvailable": bool(quote)}
    if path == "/api/metals/{id}":
        v = config(body)
        p = own(s, r, request.path_params["id"], True)
        if p.kind != "asset" or p.category != "gold" or p.archived:
            fail("贵金属资产不存在或已归档", 404)
        for k, x in v.items():
            setattr(p, k, x)
        s.flush()
        if p.autoValuation and s.scalar(
            select(MetalPrice.id)
            .where(
                MetalPrice.userId == r.userId,
                MetalPrice.metalType == p.metalType,
                MetalPrice.currency == p.currency,
                MetalPrice.date <= date.fromisoformat(today()),
            )
            .limit(1)
        ):
            value(s, r, p.id, True)
        from .quotes import invalidate

        invalidate(r.userId, "metals")
        return {"message": "贵金属估价设置已保存"}
    if path == "/api/metals/{id}/value":
        return value(s, r, request.path_params["id"], True)
    return NotImplemented
