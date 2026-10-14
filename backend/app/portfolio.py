# 项目业务：账户、独立资产和债务共用原有契约，不改变统计开关及历史语义。
from sqlalchemy import select, delete, or_, func
from .models import *
from .common import *
from .schemas import PositionInput, Meta, RevisionInput
from .queries import *
from .calculation import totals, trend
from . import transfers


def metal_performance(p, balance, has_revision):
    available = not p.get("metalType") or has_revision
    cost = (
        fixed(dec(p["metalGrams"]) * dec(p["metalCostPerGram"]), 8)
        if p.get("metalGrams") and p.get("metalCostPerGram")
        else None
    )
    return {
        "valuationAvailable": available,
        "metalCost": cost,
        "metalProfit": fixed(dec(balance) - dec(cost), 8)
        if cost and available
        else None,
    }


def list_positions(s, r, kind=None):
    if kind is not None and kind not in ("account", "asset", "debt"):
        fail("项目类型无效")
    ps = current_positions(s, r, kind)
    u = s.get(User, r.userId)
    rs = current_rates(s, r, [p["currency"] for p in ps], u.baseCurrency, today())
    amounts = {i["id"]: i for i in totals(ps, rs, u.baseCurrency, today())["items"]}
    activity = set(
        s.scalars(
            select(Revision.positionId).where(
                Revision.positionId.in_([p["id"] for p in ps]),
                Revision.effectiveDate >= business_date(today()),
                Revision.effectiveDate < business_date(today()) + timedelta(days=1),
            )
        )
    )
    out = []
    for p in ps:
        revisions = p.pop("revisions")
        p.pop("userId")
        amount = decimal_string(revisions[0]["amount"]) if revisions else "0"
        out.append(
            {
                **p,
                "activityDate": today() if p["id"] in activity else None,
                **metal_performance(p, amount, bool(revisions)),
                "amount": amount,
                "converted": amounts[p["id"]]["converted"],
                "rateDate": amounts[p["id"]]["rateDate"],
            }
        )
    return out


def detail(s, r, id):
    own(s, r, id)
    p = current_positions(s, r, id=id)[0]
    revs = p.pop("revisions")
    p.pop("userId")
    amount = decimal_string(revs[0]["amount"]) if revs else "0"
    return {**p, **metal_performance(p, amount, bool(revs)), "amount": amount}


def icon_visible(s, r, id, previous_id=None):
    if id:
        icon = s.get(Icon, id)
        if not icon or not (icon.shared or icon.ownerId == r.userId):
            fail("图标不存在或无权使用")
        # 已使用的图标继续显示和保存，禁止将下架图标新增到其他账户。
        if icon.deletedAt is not None and id != previous_id:
            fail("该图标已下架，请选择其他图标")


def create(s, r, body):
    v = PositionInput.model_validate(body).model_dump(exclude_unset=True)
    defaults = {"notes": "", "archived": False, "hidden": False}
    v = {**defaults, **v}
    amount = v.pop("amount")
    when = business_date(v.pop("date"))
    icon_visible(s, r, v.get("iconId"))
    p = Position(**v, userId=r.userId)
    s.add(p)
    s.flush()
    rev = Revision(
        positionId=p.id,
        amount=amount,
        effectiveDate=when,
        notes=p.notes,
        reason="initial",
    )
    s.add(rev)
    s.flush()
    from .quotes import invalidate

    invalidate(r.userId)
    return {"id": p.id}


def edit(s, r, id, body):
    parsed = Meta.model_validate(body)
    v = parsed.model_dump(exclude_unset=True)
    v = {"notes": "", "archived": False, "hidden": False, **v}
    p = own(s, r, id, True)
    if (
        p.kind == "account"
        and v["category"] in ("credit_card", "loan")
        and p.side != "liability"
    ):
        fail("信用卡和贷款账户必须为负债")
    icon_visible(s, r, v.get("iconId"), p.iconId)
    for k, val in v.items():
        setattr(p, k, val)
    if p.kind == "asset" and p.category != "gold":
        p.metalType = None
        p.metalGrams = None
        p.metalCostPerGram = None
        p.metalPurity = dec(1)
        p.autoValuation = False
    return {"ok": True}


def quick_meta(s, r, id, body, repayment=False):
    keys = (
        {"month", "expectedMonth", "expectedUpdatedAt"}
        if repayment
        else {"included", "expectedIncluded", "expectedUpdatedAt"}
    )
    if (
        not isinstance(body, dict)
        or set(body) - keys
        or not (
            {"month", "expectedMonth"}
            if repayment
            else {"included", "expectedIncluded"}
        ).issubset(body)
    ):
        fail("标记参数无效")
    p = own(s, r, id, True)
    if body.get("expectedUpdatedAt") and iso(p.updatedAt) != body["expectedUpdatedAt"]:
        fail("项目已变化，请刷新后重试", 409)
    if repayment:
        if p.kind != "account" or p.side != "liability":
            fail("仅欠款账户支持还款月份标记")
        if p.archived:
            fail("请先恢复归档账户", 409)
        for k in ("month", "expectedMonth"):
            value = body[k]
            if value is not None and (
                not __import__("re").fullmatch(
                    r"(19|[2-9]\d)\d{2}-(0[1-9]|1[0-2])", value
                )
                or value > today()[:7]
            ):
                fail("不能标记未来还款月份")
        if p.lastRepaymentMonth != body["expectedMonth"]:
            fail("还款标记已变化，请刷新后重试", 409)
        previous = p.lastRepaymentMonth
        p.lastRepaymentMonth = body["month"]
        s.flush()
        return {
            "lastRepaymentMonth": p.lastRepaymentMonth,
            "previousMonth": previous,
            "updatedAt": p.updatedAt,
        }
    if p.kind != "asset":
        fail("仅独立资产支持此快速统计开关")
    if type(body["included"]) is not bool or type(body["expectedIncluded"]) is not bool:
        fail("标记参数无效")
    if p.included != body["expectedIncluded"]:
        fail("标记已变化，请刷新后重试", 409)
    p.included = body["included"]
    s.flush()
    return {"included": p.included, "updatedAt": p.updatedAt}


def deletion(s, r, id):
    p = own(s, r, id)

    def count(model, condition):
        return s.scalar(select(func.count()).select_from(model).where(condition))

    history_count = count(Revision, Revision.positionId == id)
    movement_count = count(
        Transfer, or_(Transfer.sourceId == id, Transfer.targetId == id)
    )
    schedule_count = count(
        Schedule, or_(Schedule.sourceId == id, Schedule.targetId == id)
    )
    links = count(
        PositionLink, or_(PositionLink.sourceId == id, PositionLink.targetId == id)
    )
    return dict(
        name=p.name,
        historyCount=history_count,
        movementCount=movement_count,
        scheduleCount=schedule_count,
        linkCount=links,
        canDelete=movement_count == 0 and schedule_count == 0,
    )


def remove(s, r, id, body):
    p = own(s, r, id, True)
    if not isinstance(body, dict) or set(body) != {"confirmation"}:
        fail("请输入完整项目名称确认删除")
    if body["confirmation"] != p.name:
        fail("请输入完整项目名称确认删除")
    dependencies = deletion(s, r, id)
    if dependencies["movementCount"]:
        fail(
            "项目存在资金往来，请先撤销相关转账、借贷或还款记录，或选择归档保留历史",
            409,
        )
    if dependencies["scheduleCount"]:
        fail("项目被定时计划使用，请先删除相关计划，或选择归档", 409)
    s.delete(p)
    from .quotes import invalidate

    invalidate(r.userId)
    return {"ok": True}


def revise(s, r, id, body, revision_id=None):
    v = RevisionInput.parse(body)
    p = own(s, r, id, True)
    if p.archived:
        fail("请先恢复归档项目", 409)
    if v["amount"].startswith("-") and p.kind != "account":
        fail("仅账户支持负余额")
    when = business_date(v["date"])
    if revision_id:
        rev = one(s, Revision, id=revision_id, positionId=id)
        if not rev:
            fail("历史记录不存在", 404)
        if rev.reason in PAIRED:
            fail("请在资金往来中修改完整配对记录", 409)
        replay = transfers.capture_replay(s, r, [id])
        rev.amount = v["amount"]
        rev.effectiveDate = when
        rev.notes = v["notes"]
        rev.reason = "correction"
        replay()
        return {"ok": True}
    if v["reason"] in PAIRED:
        fail("请使用账户转账接口")
    last_transfer = s.scalar(
        select(Revision)
        .where(Revision.positionId == id, Revision.reason.in_(PAIRED))
        .order_by(Revision.effectiveDate.desc(), Revision.sequence.desc())
        .limit(1)
    )
    if last_transfer and when < last_transfer.effectiveDate:
        fail("余额调整时间不能早于已有转账；请使用当前时间调整", 409)
    if v["reason"] == "repayment":
        if p.side != "liability":
            fail("还款记录只能用于负债")
        prior = latest(s, id, when + timedelta(milliseconds=1))
        if not prior or dec(v["amount"]) > dec(prior.amount):
            fail("还款后的欠款不能高于该业务日期的原欠款")
    rev = Revision(
        positionId=id,
        amount=v["amount"],
        effectiveDate=when,
        notes=v["notes"],
        reason=v["reason"],
    )
    s.add(rev)
    s.flush()
    s.refresh(rev)
    return row(rev)


def delete_revision(s, r, id, revision_id):
    p = own(s, r, id, True)
    if p.archived:
        fail("请先恢复归档项目", 409)
    rev = one(s, Revision, id=revision_id, positionId=id)
    if not rev:
        fail("历史记录不存在", 404)
    if rev.reason in PAIRED:
        t = one(s, Transfer, sourceRevisionId=rev.id) or one(
            s, Transfer, targetRevisionId=rev.id
        )
        if not t:
            fail("配对记录不完整，无法删除", 409)
        return transfers.change(s, r, t.id)
    replay = transfers.capture_replay(s, r, [id])
    s.delete(rev)
    replay()
    return {"ok": True}


def links(s, r, id, body):
    if (
        not isinstance(body, dict)
        or set(body) != {"targetIds"}
        or not isinstance(body["targetIds"], list)
        or len(body["targetIds"]) > 20
    ):
        fail("关联参数无效")
    ids = body["targetIds"]
    p = own(s, r, id, True)
    if p.kind != "debt":
        fail("债务不存在", 404)
    if len(set(ids)) != len(ids) or id in ids:
        fail("关联不能重复或指向自身")
    targets = s.scalars(
        positions_query(r).where(
            Position.id.in_(ids), Position.kind.in_(["account", "asset"])
        )
    ).all()
    if len(targets) != len(ids):
        fail("只能关联自己的账户或资产")
    s.execute(delete(PositionLink).where(PositionLink.sourceId == id))
    s.add_all([PositionLink(sourceId=id, targetId=target) for target in ids])
    return {"ok": True}


def overview(s, r):
    if not r.agent:
        from .quotes import daily

        daily(r.userId, "rates")
        daily(r.userId, "metals")
    u = s.get(User, r.userId)
    ps = current_positions(s, r)
    for p in ps:
        p["included"] = p["included"] and (
            p["kind"] != "asset" or u.includeIndependentAssets
        )
    return {
        "baseCurrency": u.baseCurrency,
        **totals(
            ps,
            current_rates(s, r, [p["currency"] for p in ps], u.baseCurrency, today()),
            u.baseCurrency,
            today(),
        ),
        "revealed": r.revealed,
    }


def trend_data(s, r, query):
    from .schemas import check_date

    if set(query) - {"from", "to", "grain"}:
        fail("趋势参数无效")
    end = query.get("to", today())
    start = query.get(
        "from", (date.fromisoformat(today()) - timedelta(days=89)).isoformat()
    )
    grain = query.get("grain", "day")
    check_date(start)
    check_date(end)
    if grain not in ("day", "week", "month"):
        fail("趋势粒度无效")
    maximum = {"day": 365, "week": 1095, "month": 3652}[grain]
    span = (date.fromisoformat(end) - date.fromisoformat(start)).days
    if span < 0 or span > maximum:
        fail("日期范围超出限制（" + str(maximum + 1) + " 天）")
    u = s.get(User, r.userId)
    ps = current_positions(
        s, r, all_history=True, start=start, end=end, daily_only=True
    )
    for p in ps:
        p["included"] = p["included"] and (
            p["kind"] != "asset" or u.includeIndependentAssets
        )
    return {
        "from": start,
        "to": end,
        "grain": grain,
        "baseCurrency": u.baseCurrency,
        "revealed": r.revealed,
        "items": trend(
            ps,
            rate_history(s, r, [p["currency"] for p in ps], u.baseCurrency, start, end),
            u.baseCurrency,
            start,
            end,
            grain,
        ),
    }
