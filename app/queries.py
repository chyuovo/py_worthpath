import base64,json
from datetime import timedelta
from sqlalchemy import select,func,and_,or_
from .models import Position,Revision,ExchangeRate,PositionLink,User
from .common import *
from .calculation import history_row
def positions_query(r):
    q=select(Position).where(Position.userId==r.userId)
    return q if r.revealed else q.where(Position.hidden.is_(False))
def own(s,r,id,lock=False):
    q=positions_query(r).where(Position.id==id)
    if lock:q=q.with_for_update()
    p=s.scalar(q)
    if not p:fail("项目不存在",404)
    return p
def latest(s,id,before=None):
    q=select(Revision).where(Revision.positionId==id)
    if before:q=q.where(Revision.effectiveDate<before)
    return s.scalar(q.order_by(Revision.effectiveDate.desc(),Revision.sequence.desc()).limit(1))
def current_positions(s,r,kind=None,id=None,all_history=False,start=None,end=None):
    q=positions_query(r)
    if kind:q=q.where(Position.kind==kind)
    if id:q=q.where(Position.id==id)
    ps=s.scalars(q.order_by(Position.createdAt.desc(),Position.id.desc())).all()
    output=[]
    for p in ps:
        v=row(p)
        if all_history:
            rq=select(Revision).where(Revision.positionId==p.id)
            if start:rq=rq.where(Revision.effectiveDate>=business_date(start))
            if end:rq=rq.where(Revision.effectiveDate<business_date(end)+timedelta(days=1))
            revs=list(s.scalars(rq.order_by(Revision.effectiveDate,Revision.sequence)))
            if start:
                seed=latest(s,p.id,business_date(start))
                if seed:revs.insert(0,seed)
        else:
            rev=latest(s,p.id,business_date(today())+timedelta(days=1));revs=[rev] if rev else []
        v["revisions"]=[row(x) for x in revs]
        links=s.scalars(select(PositionLink).where(PositionLink.sourceId==p.id)).all()
        outgoing=[]
        for link in links:
            target=s.scalar(positions_query(r).where(Position.id==link.targetId))
            if target:outgoing.append({**row(link),"target":{"name":target.name,"kind":target.kind}})
        v["outgoing"]=outgoing;output.append(v)
    return output
def rates(s,r):return [row(x) for x in s.scalars(select(ExchangeRate).where(ExchangeRate.userId==r.userId)).all()]
def page_input(query):
    if set(query)-{"limit","cursor","positionId","from","to"}:fail("分页参数无效")
    try:
        limit=int(query.get("limit",50))
        if not 1<=limit<=100:raise ValueError()
        cursor=None
        if query.get("cursor"):
            raw=query["cursor"]
            if len(raw)>512:raise ValueError()
            cursor=json.loads(base64.urlsafe_b64decode(raw+"="*(-len(raw)%4)))
            if set(cursor)!={"time","key"}:raise ValueError()
            cursor=(datetime.fromisoformat(cursor["time"].replace("Z","+00:00")).replace(tzinfo=None),cursor["key"])
        if query.get("from") and query.get("to") and query["from"]>query["to"]:fail("开始日期不能晚于结束日期")
        from .schemas import check_date
        for key in ("from","to"):
            if key in query:check_date(query[key])
        return {**query,"limit":limit,"cursor":cursor}
    except (ValueError,TypeError,KeyError):fail("分页参数无效")
def encode_cursor(time,key):
    return base64.urlsafe_b64encode(json.dumps({"time":iso(time),"key":str(key)},separators=(",",":")).encode()).decode().rstrip("=")
def history(s,r,query):
    q=page_input(query)
    pq=positions_query(r)
    if q.get("positionId"):pq=pq.where(Position.id==q["positionId"])
    ps={p.id:p for p in s.scalars(pq)}
    rq=select(Revision).where(Revision.positionId.in_(ps))
    if q.get("from"):rq=rq.where(Revision.effectiveDate>=business_date(q["from"]))
    if q.get("to"):rq=rq.where(Revision.effectiveDate<business_date(q["to"])+timedelta(days=1))
    if q["cursor"]:
        t,k=q["cursor"]
        try:k=int(k)
        except ValueError:fail("分页游标无效")
        rq=rq.where(or_(Revision.effectiveDate<t,and_(Revision.effectiveDate==t,Revision.sequence<k)))
    records=s.scalars(rq.order_by(Revision.effectiveDate.desc(),Revision.sequence.desc()).limit(q["limit"]+1)).all()
    items=[]
    for rev in records[:q["limit"]]:
        prior=s.scalar(select(Revision).where(Revision.positionId==rev.positionId,or_(Revision.effectiveDate<rev.effectiveDate,and_(Revision.effectiveDate==rev.effectiveDate,Revision.sequence<rev.sequence))).order_by(Revision.effectiveDate.desc(),Revision.sequence.desc()).limit(1))
        items.append(history_row(row(ps[rev.positionId]),row(rev),prior.amount if prior else 0))
    last=records[q["limit"]-1] if len(records)>q["limit"] else None
    return {"items":items,"nextCursor":encode_cursor(last.effectiveDate,last.sequence) if last else None,"revealed":r.revealed}
