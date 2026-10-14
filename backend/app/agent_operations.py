# Agent 写入：原子校验状态、幂等键及授权；网页草稿须由本人明确确认。
import json,re
from sqlalchemy import select,update
from .common import *
from .models import *
from . import oauth,agent_tools
from .queries import positions_query,latest
def stable(value):return json.dumps(serializable(value),ensure_ascii=False,sort_keys=True,separators=(",",":"))
def state(s,user_id):
    u=s.get(User,user_id);keys=["username","baseCurrency","hiddenMenus","showNotes","idleMinutes","accountGroupOrder","sessionHours","requireHiddenPassword","overviewCards","includeIndependentAssets"]
    profile={k:getattr(u,k) for k in keys};ps=[]
    for p in s.scalars(select(Position).where(Position.userId==user_id).order_by(Position.id)):
        v=row(p);v["revisions"]=[row(x) for x in s.scalars(select(Revision).where(Revision.positionId==p.id).order_by(Revision.id))];v["outgoing"]=[row(x) for x in s.scalars(select(PositionLink).where(PositionLink.sourceId==p.id).order_by(PositionLink.id))];ps.append(v)
    data=[profile,ps]
    for model in (Transfer,Schedule,ExchangeRate,MetalPrice):data.append([row(x) for x in s.scalars(select(model).where(model.userId==user_id).order_by(model.id))])
    data.append([{k:getattr(x,k) for k in ("id","name","hash","shared")} for x in s.scalars(select(Icon).where(Icon.ownerId==user_id).order_by(Icon.id))])
    return digest(stable(data))
def permission(s,g,tool,p):
    u=s.get(User,g.userId)
    if u.banned or u.mustChangePassword:fail("账号不可用",403)
    if u.role=="readonly" and tool["scope"]!="read":fail("只读账号不能提交写入或草稿",403)
    if "read" not in g.scopes:fail("缺少 read 权限",403)
    mode="direct" if "write" in g.scopes else "draft" if "draft" in g.scopes else "readonly"
    if tool["scope"]!="read":
        if mode=="readonly":fail("本连接只有只读权限",403)
        if "hidden_write" not in g.scopes and (p.get("hidden") is True or (isinstance(p.get("data"),dict) and p["data"].get("hidden") is True)):fail("缺少隐藏账户修改权限",403)
    return mode
def view(op):
    v=dict(operationId=op.id,tool=op.tool,status="expired" if op.status=="pending" and op.expiresAt<now() else op.status,expiresAt=op.expiresAt,result=op.result)
    if op.status=="pending":v["confirmationUrl"]=oauth.web_link("agent_operation",op.id)
    return v
def call(s,g,name,params):
    p=agent_tools.validate(name,params);tool=agent_tools.TOOLS[name]
    permission(s,g,tool,p)
    if tool["scope"]=="read":return agent_tools.run(s,g,name,p)
    key=p.pop("idempotencyKey");expected=p.pop("expectedState")
    hash=digest(stable(dict(tool=name,parameters=p,expectedState=expected)))
    s.scalar(select(User).where(User.id==g.userId).with_for_update())
    g=oauth.grant(s,g.id);mode=permission(s,g,tool,p)
    old=one(s,AgentOperation,userId=g.userId,key=key)
    if old:
        if old.hash!=hash or old.grantId!=g.id:fail("幂等键已用于不同参数或连接",409)
        return view(old)
    snapshot=state(s,g.userId)
    if snapshot!=expected:fail("账目已变化，请重新读取 state_get 和数据后使用新幂等键",409)
    op=AgentOperation(userId=g.userId,grantId=g.id,key=key,hash=hash,tool=name,parameters=serializable(p),snapshot=snapshot,expiresAt=now()+timedelta(minutes=10));s.add(op);s.flush()
    if mode=="draft":return view(op)
    result=agent_tools.run(s,g,name,p);s.flush()
    op.status="completed";op.result=serializable(result);op.completedAt=now()
    return view(op)
def get(s,user_id,id,grant_id=None):
    op=one(s,AgentOperation,id=id,userId=user_id)
    if not op or (grant_id and op.grantId!=grant_id):fail("操作不存在",404)
    return op
def preview(s,user_id,id):
    op=get(s,user_id,id);g=oauth.grant(s,op.grantId,user_id);p=op.parameters;tool=agent_tools.TOOLS[op.tool]
    r=oauth.context(s,g);references={}
    def collect(value):
        if isinstance(value,str) and re.fullmatch("[a-f0-9-]{36}",value,re.I):return {value}
        if isinstance(value,list):return set().union(*(collect(x) for x in value)) if value else set()
        if isinstance(value,dict):return collect(list(value.values()))
        return set()
    ids=collect(p)
    for x in s.scalars(positions_query(r).where(Position.id.in_(ids))):references[x.id]={k:getattr(x,k) for k in ("id","name","currency","side","kind")}
    for plan in s.scalars(select(Schedule).where(Schedule.userId==user_id,Schedule.id.in_(ids))):
        valid=s.scalars(positions_query(r).where(Position.id.in_([plan.sourceId,plan.targetId]))).all()
        if len(valid)==(2 if plan.targetId else 1):references[plan.id]={"name":plan.name,"kind":"schedule"}
    current=None
    if op.tool in ("movement_update","movement_delete"):
        from .transfers import visible_transfer,describe
        t=s.scalar(visible_transfer(s,r,id=p["id"]))
        if t:
            current={k:v for k,v in describe(s,t).items() if k in ("operation","sourceId","targetId","amount","received","fee","date","notes")}
            for pid in (t.sourceId,t.targetId):
                pos=s.get(Position,pid);references[pid]={"name":pos.name,"currency":pos.currency}
    elif op.tool in ("history_update","history_delete","balance_record"):
        q=select(Revision).where(Revision.positionId==p["id"],Revision.positionId.in_(positions_query(r).with_only_columns(Position.id)))
        if p.get("revisionId"):q=q.where(Revision.id==p["revisionId"])
        rev=s.scalar(q.order_by(Revision.effectiveDate.desc(),Revision.sequence.desc()).limit(1))
        if rev:current=dict(id=p["id"],amount=fixed(rev.amount),date=business_time(rev.effectiveDate),notes=rev.notes)
    impact=dict(parameters=p,references=references)
    if current is not None:impact["current"]=current
    return {**view(op),"impact":impact,"connectionName":g.name,"destructive":tool["destructive"],"description":tool["description"]}
def confirm(s,r,id,approve,advance=True):
    s.scalar(select(User).where(User.id==r.userId).with_for_update())
    op=get(s,r.userId,id)
    if op.status!="pending" or op.expiresAt<=now():fail("操作已完成或失效",409)
    if not approve:op.status="cancelled";op.completedAt=now();return view(op)
    g=oauth.grant(s,op.grantId,r.userId);tool=agent_tools.TOOLS[op.tool];permission(s,g,tool,op.parameters)
    if state(s,r.userId)!=op.snapshot:fail("账目已变化，请取消并重新创建操作",409)
    result=agent_tools.run(s,g,op.tool,op.parameters);s.flush()
    if op.tool=="position_create" and advance:
        snapshot=state(s,r.userId)
        s.execute(update(AgentOperation).where(AgentOperation.userId==r.userId,AgentOperation.grantId==g.id,AgentOperation.tool=="position_create",AgentOperation.status=="pending",AgentOperation.snapshot==op.snapshot,AgentOperation.id!=op.id,AgentOperation.expiresAt>now()).values(snapshot=snapshot))
    op.status="completed";op.result=serializable(result);op.completedAt=now();return view(op)
def confirm_batch(s,r,body):
    if not isinstance(body,dict) or set(body)!={"operationIds","approve"} or type(body["approve"]) is not bool or not isinstance(body["operationIds"],list) or not 1<=len(body["operationIds"])<=100 or len(set(body["operationIds"]))!=len(body["operationIds"]):fail("批量确认参数无效")
    s.scalar(select(User).where(User.id==r.userId).with_for_update())
    rows=[get(s,r.userId,id) for id in body["operationIds"]]
    if body["approve"] and all(row.status=="completed" for row in rows):return {"operations":[view(row) for row in rows]}
    baseline=state(s,r.userId)
    for op in rows:
        if op.status!="pending" or op.expiresAt<=now():fail("部分草稿已完成或失效，请刷新后重新选择",409)
        if body["approve"]:
            if op.snapshot!=baseline:fail("账目已变化，请取消并重新创建操作",409)
            g=oauth.grant(s,op.grantId,r.userId);permission(s,g,agent_tools.TOOLS[op.tool],op.parameters)
    results=[]
    for op in rows:
        if body["approve"]:op.snapshot=state(s,r.userId)
        results.append(confirm(s,r,op.id,body["approve"]))
        s.flush()
    return {"operations":results}
