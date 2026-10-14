# 定时计划：由页面按需执行，单批最多 20 项；不进行真实资金划转。
from sqlalchemy import select, or_
from .common import *
from .models import *
from .queries import positions_query, latest, own
from .schemas import money, check_date
from .transfers import execute, lock_positions


def parse(body):
    keys = {
        "name",
        "operation",
        "sourceId",
        "targetId",
        "amount",
        "received",
        "nextAt",
        "intervalDays",
        "notes",
    }
    if (
        not isinstance(body, dict)
        or set(body) - keys
        or not {
            "name",
            "operation",
            "sourceId",
            "amount",
            "nextAt",
            "intervalDays",
        }.issubset(body)
    ):
        fail("计划参数无效")
    v = {"targetId": None, "received": "0", "notes": "", **body}
    if not isinstance(v["name"], str) or not 1 <= len(v["name"].strip()) <= 100:
        fail("计划名称无效")
    v["name"] = v["name"].strip()
    if v["operation"] not in ("expense", "transfer"):
        fail("计划操作无效")
    money(v["amount"], False, True)
    money(v["received"], False)
    if not isinstance(v["nextAt"], str) or len(v["nextAt"]) != 16:
        fail("计划时间无效")
    check_date(v["nextAt"], True)
    try:
        v["intervalDays"] = int(v["intervalDays"])
    except (TypeError, ValueError):
        fail("计划间隔无效")
    if (
        not 0 <= v["intervalDays"] <= 3650
        or not isinstance(v["notes"], str)
        or len(v["notes"]) > 2000
    ):
        fail("计划参数无效")
    if v["operation"] == "transfer" and (
        not v["targetId"] or v["targetId"] == v["sourceId"] or dec(v["received"]) <= 0
    ):
        fail("转账计划须选择不同账户并填写到账金额")
    return v


def visible(s, r):
    ids = (
        positions_query(r)
        .where(Position.kind == "account")
        .with_only_columns(Position.id)
    )
    return select(Schedule).where(
        Schedule.userId == r.userId,
        Schedule.sourceId.in_(ids),
        or_(Schedule.targetId.is_(None), Schedule.targetId.in_(ids)),
    )


def validate_accounts(s, r, v):
    ids = [v["sourceId"]] + ([v["targetId"]] if v["targetId"] else [])
    lock_positions(s, r, ids)
    ps = s.scalars(
        positions_query(r).where(
            Position.id.in_(ids),
            Position.kind == "account",
            Position.archived.is_(False),
        )
    ).all()
    if len(ps) != len(ids) or (
        v["operation"] == "expense" and any(p.side != "asset" for p in ps)
    ):
        fail("请选择启用的账户（支出计划使用资产账户）")
    if v["operation"] == "expense" and v["targetId"]:
        fail("支出计划无需转入账户")
    if (
        v["operation"] == "transfer"
        and ps[0].currency == ps[1].currency
        and dec(v["amount"]) != dec(v["received"])
    ):
        fail("同币种转出与到账金额必须一致")


def occurrence_id(id, when):
    h = digest(id + ":" + iso(when))
    return h[:8] + "-" + h[8:12] + "-4" + h[13:16] + "-a" + h[17:20] + "-" + h[20:32]


def run(s, r, atomic_batch=False):
    current = now()
    due = s.scalars(
        visible(s, r)
        .where(Schedule.enabled.is_(True), Schedule.nextAt <= current)
        .order_by(Schedule.nextAt, Schedule.id)
        .limit(20)
    ).all()
    executed = 0
    errors = []
    has_more = len(due) == 20
    for candidate in due:
        try:
            with s.begin_nested():
                plan = s.scalar(
                    visible(s, r)
                    .where(
                        Schedule.id == candidate.id,
                        Schedule.enabled.is_(True),
                        Schedule.nextAt <= current,
                    )
                    .with_for_update()
                )
                if not plan:
                    continue
                old_next = plan.nextAt
                request_id = occurrence_id(plan.id, old_next)
                day = business_time(current)
                memo = (
                    "计划："
                    + plan.name
                    + " · 应执行时间 "
                    + business_time(old_next)
                    + "\n"
                    + plan.notes
                )[:2000]
                if plan.operation == "transfer":
                    execute(
                        s,
                        r,
                        dict(
                            sourceId=plan.sourceId,
                            targetId=plan.targetId,
                            amount=fixed(plan.amount),
                            received=fixed(plan.received),
                            fee="0",
                            date=day,
                            notes=memo,
                            requestId=request_id,
                        ),
                    )
                else:
                    p = own(s, r, plan.sourceId, True)
                    if p.kind != "account" or p.side != "asset" or p.archived:
                        fail("计划账户已归档或不可用")
                    prev = latest(s, p.id)
                    after = dec(prev.amount if prev else 0) - dec(plan.amount)
                    if abs(after) >= dec("10000000000000000"):
                        fail("变更后的金额超出支持范围")
                    s.add(
                        Revision(
                            id=request_id,
                            positionId=p.id,
                            amount=after,
                            effectiveDate=business_date(day),
                            notes=memo,
                            reason="scheduled_expense",
                        )
                    )
                if plan.intervalDays:
                    plan.nextAt = old_next + timedelta(days=plan.intervalDays)
                    if plan.nextAt <= current:
                        has_more = True
                else:
                    plan.enabled = False
                    plan.completed = True
                s.flush()
                executed += 1
        except Exception as e:
            if atomic_batch:
                raise
            errors.append(
                {
                    "id": candidate.id,
                    "message": e.detail
                    if isinstance(e, HTTPException) and e.status_code == 400
                    else "计划未执行，请刷新或检查账户状态后重试",
                }
            )
    return {"executed": executed, "errors": errors, "hasMore": has_more}


def dispatch(s, r, request, response, body):
    path = request.scope["route"].path
    method = request.method
    p = request.path_params
    if path == "/api/schedules/run":
        return run(s, r)
    if path == "/api/schedules":
        if method == "GET":
            return [
                {
                    **{k: v for k, v in row(x).items() if k != "userId"},
                    "nextAt": business_time(x.nextAt),
                }
                for x in s.scalars(visible(s, r).order_by(Schedule.nextAt, Schedule.id))
            ]
        v = parse(body)
        validate_accounts(s, r, v)
        v["nextAt"] = business_date(v["nextAt"])
        plan = Schedule(userId=r.userId, **v)
        s.add(plan)
        s.flush()
        return {"id": plan.id}
    if path == "/api/schedules/{id}":
        plan = s.scalar(visible(s, r).where(Schedule.id == p["id"]).with_for_update())
        if not plan:
            fail("计划不存在", 404)
        if method == "DELETE":
            s.delete(plan)
            return {"ok": True}
        if method == "PATCH":
            if (
                not isinstance(body, dict)
                or set(body) != {"enabled"}
                or type(body["enabled"]) is not bool
            ):
                fail("计划参数无效")
            if plan.completed and body["enabled"]:
                fail("一次性计划已完成，请新建计划")
            plan.enabled = body["enabled"]
        else:
            if plan.completed:
                fail("一次性计划已完成，请新建计划")
            v = parse(body)
            validate_accounts(s, r, v)
            v["nextAt"] = business_date(v["nextAt"])
            for k, value in v.items():
                setattr(plan, k, value)
        return {"ok": True}
    return NotImplemented
