# 配对记账：双边余额与历史共用事务；修改或撤销后重算后续配对记录。
"""Shared, transactional paired movements and historical replay."""

from sqlalchemy import select, delete, or_, and_
from .models import *
from .common import *
from .queries import own, latest, positions_query, page_input, encode_cursor
from .schemas import TransferInput
from .calculation import movement_deltas


def lock_positions(s, r, ids):
    return s.scalars(
        select(Position)
        .where(Position.userId == r.userId, Position.id.in_(sorted(set(ids))))
        .order_by(Position.id)
        .with_for_update()
    ).all()


def execute(s, r, body):
    v = TransferInput.parse(body)
    when = business_date(v["date"])
    # 固定锁顺序后再读取余额和幂等记录，防止并发双重记账及交叉死锁。
    lock_positions(s, r, [v["sourceId"], v["targetId"]])
    # 同一请求键仅允许完全相同的参数重试，不能借重试修改已完成操作。
    if v["requestId"]:
        old = one(s, Transfer, id=v["requestId"], userId=r.userId)
        if old:
            if (
                any(
                    getattr(old, k) != v[k]
                    for k in ("sourceId", "targetId", "operation", "notes")
                )
                or old.effectiveDate != when
                or any(
                    dec(getattr(old, k)) != dec(v[k])
                    for k in ("amount", "received", "fee")
                )
            ):
                fail("转账请求标识已使用，请刷新后重试", 409)
            return {"id": old.id}
    accounts = s.scalars(
        positions_query(r).where(
            Position.id.in_([v["sourceId"], v["targetId"]]),
            Position.archived.is_(False),
        )
    ).all()
    if len(accounts) != 2:
        fail("只能在自己的启用账户之间转账（隐藏账户须先解锁）")
    source = next(p for p in accounts if p.id == v["sourceId"])
    target = next(p for p in accounts if p.id == v["targetId"])
    op = v["operation"]
    if (
        source.kind != "account"
        or (op != "transfer" and source.side != "asset")
        or (
            target.kind != "account"
            if op == "transfer"
            else not (
                (target.kind == "debt" or (op == "repay" and target.kind == "account"))
                and target.side
                == ("liability" if op in ("borrow", "repay") else "asset")
            )
        )
    ):
        fail("请选择资产账户及对应债务；还款也可选择负债账户")
    prev = {p.id: latest(s, p.id) for p in accounts}
    if any(x and x.effectiveDate > when for x in prev.values()):
        fail("转账时间不能早于任一账户的最新余额记录，请以当前余额转账", 409)
    if source.currency == target.currency and dec(v["amount"]) != dec(v["received"]):
        fail("同币种转出与到账金额必须一致，手续费单独填写")
    sd, td, sreason, treason = movement_deltas(
        op, v["amount"], v["received"], v["fee"], source.side, target.side
    )
    after_source = dec(prev[source.id].amount if prev[source.id] else 0) + sd
    after_target = dec(prev[target.id].amount if prev[target.id] else 0) + td
    if target.kind == "debt" and after_target < 0:
        fail("收款或还款不能超过剩余债务")
    if max(abs(after_source), abs(after_target)) >= dec("10000000000000000"):
        fail("变更后的金额超出支持范围")
    outgoing = Revision(
        positionId=source.id,
        amount=after_source,
        effectiveDate=when,
        notes=v["notes"],
        reason=sreason,
    )
    incoming = Revision(
        positionId=target.id,
        amount=after_target,
        effectiveDate=when,
        notes=v["notes"],
        reason=treason,
    )
    s.add_all([outgoing, incoming])
    s.flush()
    t = Transfer(
        userId=r.userId,
        operation=op,
        sourceId=source.id,
        targetId=target.id,
        sourceRevisionId=outgoing.id,
        targetRevisionId=incoming.id,
        sourceCurrency=source.currency,
        targetCurrency=target.currency,
        amount=v["amount"],
        received=v["received"],
        fee=v["fee"],
        effectiveDate=when,
        notes=v["notes"],
    )
    if v["requestId"]:
        t.id = v["requestId"]
    s.add(t)
    s.flush()
    if (
        op != "transfer"
        and target.kind == "debt"
        and not one(s, PositionLink, sourceId=target.id, targetId=source.id)
    ):
        s.add(PositionLink(sourceId=target.id, targetId=source.id))
    return {"id": t.id}


# 绝对余额作为锚点；转账和计划支出保留原增量，按业务时间与自增顺序回放。
def capture_replay(s, r, ids):
    lock_positions(s, r, ids)
    records = s.scalars(
        select(Revision)
        .where(Revision.positionId.in_(ids))
        .order_by(Revision.effectiveDate, Revision.sequence)
    ).all()
    deltas = {}
    balances = {}
    for rev in records:
        if rev.reason == "scheduled_expense":
            deltas[rev.id] = dec(rev.amount) - balances.get(rev.positionId, dec(0))
        balances[rev.positionId] = dec(rev.amount)

    def replay():
        s.flush()
        transfers = s.scalars(
            select(Transfer).where(
                Transfer.userId == r.userId,
                or_(Transfer.sourceId.in_(ids), Transfer.targetId.in_(ids)),
            )
        ).all()
        for t in transfers:
            source = s.get(Position, t.sourceId)
            target = s.get(Position, t.targetId)
            sd, td, _, _ = movement_deltas(
                t.operation, t.amount, t.received, t.fee, source.side, target.side
            )
            deltas[t.sourceRevisionId] = sd
            deltas[t.targetRevisionId] = td
        current = s.scalars(
            select(Revision)
            .where(Revision.positionId.in_(ids))
            .order_by(Revision.effectiveDate, Revision.sequence)
        ).all()
        balances.clear()
        for rev in current:
            p = s.get(Position, rev.positionId)
            delta = (
                deltas.get(rev.id)
                if rev.reason in PAIRED + ["scheduled_expense"]
                else None
            )
            if rev.reason in PAIRED and delta is None:
                fail("配对记录不完整，无法重算", 409)
            amount = (
                balances.get(rev.positionId, dec(0)) + delta
                if delta is not None
                else dec(rev.amount)
            )
            if amount < 0 and p.kind != "account":
                fail("修改后债务或资产金额不能为负数")
            if abs(amount) >= dec("10000000000000000"):
                fail("重算后的金额超出支持范围")
            balances[rev.positionId] = amount
            rev.amount = amount
        s.flush()

    return replay


def visible_transfer(s, r, id=None, revision_id=None):
    q = select(Transfer).where(Transfer.userId == r.userId)
    if id:
        q = q.where(Transfer.id == id)
    if revision_id:
        q = q.where(
            or_(
                Transfer.sourceRevisionId == revision_id,
                Transfer.targetRevisionId == revision_id,
            )
        )
    visible = positions_query(r).with_only_columns(Position.id)
    q = q.where(Transfer.sourceId.in_(visible), Transfer.targetId.in_(visible))
    return q


def describe(s, t):
    v = row(t)
    v.pop("userId")
    v.pop("importedFromId")
    v["date"] = business_time(v.pop("effectiveDate"))
    for key in ("source", "target"):
        p = s.get(Position, getattr(t, key + "Id"))
        v[key] = {"name": p.name, "kind": p.kind}
    return v


def list_transfers(s, r, query):
    q = page_input(query)
    stmt = visible_transfer(s, r)
    if q.get("positionId"):
        stmt = stmt.where(
            or_(
                Transfer.sourceId == q["positionId"],
                Transfer.targetId == q["positionId"],
            )
        )
    if q.get("from"):
        stmt = stmt.where(Transfer.effectiveDate >= business_date(q["from"]))
    if q.get("to"):
        stmt = stmt.where(
            Transfer.effectiveDate < business_date(q["to"]) + timedelta(days=1)
        )
    if q["cursor"]:
        time, key = q["cursor"]
        stmt = stmt.where(
            or_(
                Transfer.effectiveDate < time,
                and_(Transfer.effectiveDate == time, Transfer.id < key),
            )
        )
    rows = s.scalars(
        stmt.order_by(Transfer.effectiveDate.desc(), Transfer.id.desc()).limit(
            q["limit"] + 1
        )
    ).all()
    last = rows[q["limit"] - 1] if len(rows) > q["limit"] else None
    return {
        "items": [describe(s, t) for t in rows[: q["limit"]]],
        "nextCursor": encode_cursor(last.effectiveDate, last.id) if last else None,
        "revealed": r.revealed,
    }


def change(s, r, id, body=None):
    t = s.scalar(visible_transfer(s, r, id=id))
    if not t:
        fail("资金往来记录不存在", 404)
    source = own(s, r, t.sourceId)
    target = own(s, r, t.targetId)
    if source.archived or target.archived:
        fail("请先恢复归档项目", 409)
    replay = capture_replay(s, r, [source.id, target.id])
    if body is not None:
        v = TransferInput.parse(body)
        if any(v[k] != getattr(t, k) for k in ("sourceId", "targetId", "operation")):
            fail("修改记录不能更换账户或操作类型，请删除后重新创建")
        if t.sourceCurrency == t.targetCurrency and dec(v["amount"]) != dec(
            v["received"]
        ):
            fail("同币种转出与到账金额必须一致，手续费单独填写")
        for k in ("amount", "received", "fee", "notes"):
            setattr(t, k, v[k])
        t.effectiveDate = business_date(v["date"])
        for rid in (t.sourceRevisionId, t.targetRevisionId):
            rev = s.get(Revision, rid)
            rev.effectiveDate = t.effectiveDate
            rev.notes = t.notes
    else:
        ids = [t.sourceRevisionId, t.targetRevisionId]
        s.delete(t)
        s.flush()
        s.execute(delete(Revision).where(Revision.id.in_(ids)))
    replay()
    return {"ok": True}
