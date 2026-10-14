# 查询与分页：先按用户和隐藏权限过滤，再读取余额历史；游标保留业务时间及顺序。
import base64, json
from uuid import UUID
from datetime import timedelta
from sqlalchemy import select, func, and_, or_, union_all, text
from sqlalchemy.orm import aliased
from .models import Position, Revision, ExchangeRate, PositionLink, User
from .common import *
from .calculation import history_row


def positions_query(r):
    q = select(Position).where(Position.userId == r.userId)
    return q if r.revealed else q.where(Position.hidden.is_(False))


def own(s, r, id, lock=False):
    q = positions_query(r).where(Position.id == id)
    if lock:
        q = q.with_for_update()
    p = s.scalar(q)
    if not p:
        fail("项目不存在", 404)
    return p


def latest(s, id, before=None):
    q = select(Revision).where(Revision.positionId == id)
    if before:
        q = q.where(Revision.effectiveDate < before)
    return s.scalar(
        q.order_by(Revision.effectiveDate.desc(), Revision.sequence.desc()).limit(1)
    )


# 每个项目只走索引读取一条最新记录，避免 ORM 对多项目逐个查询或扫描全部历史。
def latest_many(s, ids, before):
    output = []
    for offset in range(0, len(ids), 100):
        branches = [
            select(Revision)
            .where(Revision.positionId == id, Revision.effectiveDate < before)
            .order_by(Revision.effectiveDate.desc(), Revision.sequence.desc())
            .limit(1)
            for id in ids[offset : offset + 100]
        ]
        if branches:
            output.extend(
                s.scalars(select(Revision).from_statement(union_all(*branches))).all()
            )
    return output


def current_positions(
    s, r, kind=None, id=None, all_history=False, start=None, end=None, daily_only=False
):
    q = positions_query(r)
    if kind:
        q = q.where(Position.kind == kind)
    if id:
        q = q.where(Position.id == id)
    ps = s.scalars(q.order_by(Position.createdAt.desc(), Position.id.desc())).all()
    ids = [p.id for p in ps]
    if not ids:
        return []
    grouped = {id: [] for id in ids}
    if all_history:
        rq = select(Revision).where(Revision.positionId.in_(ids))
        if start:
            rq = rq.where(Revision.effectiveDate >= business_date(start))
        if end:
            rq = rq.where(
                Revision.effectiveDate < business_date(end) + timedelta(days=1)
            )
        if daily_only:
            # 趋势仅需要北京时间每日最后余额；同日记录由业务时间和自增顺序共同排序。
            ranked = rq.add_columns(
                func.row_number()
                .over(
                    partition_by=[
                        Revision.positionId,
                        func.date(Revision.effectiveDate + text("INTERVAL 8 HOUR")),
                    ],
                    order_by=[Revision.effectiveDate.desc(), Revision.sequence.desc()],
                )
                .label("_rank")
            ).subquery()
            rq = select(aliased(Revision, ranked)).where(ranked.c._rank == 1)
        rows = list(s.scalars(rq))
        if start:
            rows = latest_many(s, ids, business_date(start)) + rows
        rows.sort(key=lambda v: (v.effectiveDate, v.sequence))
    else:
        rows = latest_many(s, ids, business_date(today()) + timedelta(days=1))
    for rev in rows:
        grouped[rev.positionId].append(row(rev))
    links_query = (
        select(PositionLink, Position)
        .join(Position, Position.id == PositionLink.targetId)
        .where(PositionLink.sourceId.in_(ids), Position.userId == r.userId)
    )
    if not r.revealed:
        links_query = links_query.where(Position.hidden.is_(False))
    outgoing = {id: [] for id in ids}
    for link, target in s.execute(links_query):
        outgoing[link.sourceId].append(
            {**row(link), "target": {"name": target.name, "kind": target.kind}}
        )
    return [
        {**row(p), "revisions": grouped[p.id], "outgoing": outgoing[p.id]} for p in ps
    ]


def current_rates(s, r, currencies, base, day):
    branches = [
        select(ExchangeRate)
        .where(
            ExchangeRate.userId == r.userId,
            ExchangeRate.currency == currency,
            ExchangeRate.baseCurrency == base,
            ExchangeRate.date <= date.fromisoformat(day),
        )
        .order_by(ExchangeRate.date.desc())
        .limit(1)
        for currency in sorted(set(currencies) - {base})
    ]
    return (
        [
            row(v)
            for v in s.scalars(
                select(ExchangeRate).from_statement(union_all(*branches))
            )
        ]
        if branches
        else []
    )


def rate_history(s, r, currencies, base, start, end):
    prior = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
    rows = [
        row(v)
        for v in s.scalars(
            select(ExchangeRate).where(
                ExchangeRate.userId == r.userId,
                ExchangeRate.currency.in_(set(currencies)),
                ExchangeRate.baseCurrency == base,
                ExchangeRate.date >= date.fromisoformat(start),
                ExchangeRate.date <= date.fromisoformat(end),
            )
        )
    ]
    return current_rates(s, r, currencies, base, prior) + rows


def rates(s, r):
    return [
        row(x)
        for x in s.scalars(
            select(ExchangeRate).where(ExchangeRate.userId == r.userId)
        ).all()
    ]


def page_input(query):
    if set(query) - {"limit", "cursor", "positionId", "from", "to"}:
        fail("分页参数无效")
    try:
        limit = int(query.get("limit", 50))
        if not 1 <= limit <= 100:
            raise ValueError()
        cursor = None
        if query.get("cursor"):
            raw = query["cursor"]
            if len(raw) > 512:
                raise ValueError()
            cursor = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
            if not isinstance(cursor, dict) or set(cursor) != {"time", "key"}:
                raise ValueError()
            if (
                not isinstance(cursor["time"], str)
                or not cursor["time"].endswith("Z")
                or not isinstance(cursor["key"], str)
                or not 1 <= len(cursor["key"]) <= 64
            ):
                raise ValueError()
            cursor = (
                datetime.fromisoformat(cursor["time"].replace("Z", "+00:00")).replace(
                    tzinfo=None
                ),
                cursor["key"],
            )
        if query.get("from") and query.get("to") and query["from"] > query["to"]:
            fail("开始日期不能晚于结束日期")
        from .schemas import check_date

        if query.get("positionId"):
            UUID(query["positionId"])
        for key in ("from", "to"):
            if key in query:
                if len(query[key]) != 10:
                    raise ValueError()
                check_date(query[key])
        return {**query, "limit": limit, "cursor": cursor}
    except (ValueError, TypeError, KeyError):
        fail("分页参数无效")


def encode_cursor(time, key):
    return (
        base64.urlsafe_b64encode(
            json.dumps(
                {"time": iso(time), "key": str(key)}, separators=(",", ":")
            ).encode()
        )
        .decode()
        .rstrip("=")
    )


def history(s, r, query):
    q = page_input(query)
    pq = positions_query(r)
    if q.get("positionId"):
        pq = pq.where(Position.id == q["positionId"])
    ps = {p.id: p for p in s.scalars(pq)}
    rq = select(Revision).where(Revision.positionId.in_(ps))
    if q.get("from"):
        rq = rq.where(Revision.effectiveDate >= business_date(q["from"]))
    if q.get("to"):
        rq = rq.where(
            Revision.effectiveDate < business_date(q["to"]) + timedelta(days=1)
        )
    if q["cursor"]:
        t, k = q["cursor"]
        try:
            k = int(k)
        except ValueError:
            fail("分页游标无效")
        rq = rq.where(
            or_(
                Revision.effectiveDate < t,
                and_(Revision.effectiveDate == t, Revision.sequence < k),
            )
        )
    records = s.scalars(
        rq.order_by(Revision.effectiveDate.desc(), Revision.sequence.desc()).limit(
            q["limit"] + 1
        )
    ).all()
    items = []
    for rev in records[: q["limit"]]:
        prior = s.scalar(
            select(Revision)
            .where(
                Revision.positionId == rev.positionId,
                or_(
                    Revision.effectiveDate < rev.effectiveDate,
                    and_(
                        Revision.effectiveDate == rev.effectiveDate,
                        Revision.sequence < rev.sequence,
                    ),
                ),
            )
            .order_by(Revision.effectiveDate.desc(), Revision.sequence.desc())
            .limit(1)
        )
        item = history_row(
            row(ps[rev.positionId]), row(rev), prior.amount if prior else 0
        )
        item["before"] = decimal_string(prior.amount) if prior else "0"
        items.append(item)
    last = records[q["limit"] - 1] if len(records) > q["limit"] else None
    return {
        "items": items,
        "nextCursor": encode_cursor(last.effectiveDate, last.sequence)
        if last
        else None,
        "revealed": r.revealed,
    }
