# 网页连接管理：用户可修改权限或撤销连接，旧草稿不会因权限提升自动执行。
from sqlalchemy import select,update
from .common import *
from .models import *
from . import oauth,auth,agent_tools,agent_operations as operations
from .mcp_contracts import CONTRACTS
def capabilities():
    return [{k:v for k,v in t.items() if k in ("name","description","scope","destructive")} for t in agent_tools.TOOLS.values()]+CONTRACTS["protocolTools"]
def dispatch(s,r,request,response,body):
    path=request.scope["route"].path;p=request.path_params
    if path=="/api/agent":
        grants=[{k:getattr(g,k) for k in ("id","name","scopes","expiresAt","refreshExpiresAt","createdAt","revokedAt","clientId")} for g in s.scalars(select(AgentGrant).where(AgentGrant.userId==r.userId).order_by(AgentGrant.createdAt.desc()).limit(100))]
        ops=[{k:getattr(g,k) for k in ("id","tool","status","expiresAt","createdAt","completedAt")} for g in s.scalars(select(AgentOperation).where(AgentOperation.userId==r.userId).order_by(AgentOperation.createdAt.desc()).limit(100))]
        calls=[{k:getattr(g,k) for k in ("id","tool","status","createdAt")} for g in s.scalars(select(AgentCall).where(AgentCall.userId==r.userId).order_by(AgentCall.createdAt.desc()).limit(100))]
        return dict(mcpUrl=oauth.urls()[0],capabilities=capabilities(),grants=grants,operations=ops,calls=calls)
    if path=="/api/agent/tokens":
        if not isinstance(body,dict) or set(body)!={"name","scopes","days","password"}:fail("令牌参数无效")
        auth.limit(request);u=s.get(User,r.userId)
        if not auth.compare(auth.password(body["password"]),u.passwordHash):fail("密码错误",403)
        name=body["name"].strip()
        if not 1<=len(name)<=100 or body["days"] not in oauth.DAYS:fail("令牌参数无效")
        g,tokens=oauth.issue(s,r.userId,name,body["scopes"],body["days"])
        return dict(id=g.id,token=tokens["access_token"],expiresAt=g.expiresAt)
    if path=="/api/agent/connections/{id}":
        g=one(s,AgentGrant,id=p["id"],userId=r.userId)
        if request.method=="DELETE":
            if g:g.revokedAt=now()
            return {"ok":True}
        if not isinstance(body,dict) or set(body)!={"scopes","password"}:fail("授权参数无效")
        auth.limit(request);u=s.scalar(select(User).where(User.id==r.userId).with_for_update())
        if not auth.compare(auth.password(body["password"]),u.passwordHash):fail("密码错误",403)
        selected=oauth.valid_scopes(body["scopes"])
        if u.role=="readonly" and {"draft","write","hidden_write"}.intersection(selected):fail("只读账号只能授予查询权限",403)
        g=s.scalar(select(AgentGrant).where(AgentGrant.id==p["id"],AgentGrant.userId==r.userId).with_for_update())
        expiry=(g.refreshExpiresAt if g.clientId else g.expiresAt) if g else None
        if not g or g.revokedAt or (expiry and expiry<=now()):fail("有效连接不存在",404)
        if set(g.scopes)!=set(selected):
            g.scopes=selected
            s.execute(update(AgentOperation).where(AgentOperation.grantId==g.id,AgentOperation.userId==r.userId,AgentOperation.status=="pending").values(status="cancelled",completedAt=now()))
        return {"ok":True}
    if path=="/api/agent/authorizations/{id}":
        if request.method=="GET":return {**oauth.pending(s,p["id"]),"canWrite":s.get(User,r.userId).role!="readonly"}
        return oauth.consent(s,r,p["id"],body)
    if path=="/api/agent/drafts":
        q=select(AgentOperation).where(AgentOperation.userId==r.userId,AgentOperation.status=="pending",AgentOperation.expiresAt>now())
        cursor=request.query_params.get("cursor")
        if cursor:q=q.where(AgentOperation.id>cursor)
        rows=s.scalars(q.order_by(AgentOperation.id).limit(51)).all();items=[]
        for op in rows[:50]:
            try:items.append(operations.preview(s,r.userId,op.id))
            except HTTPException:items.append(dict(operationId=op.id,tool=op.tool,status="unavailable",expiresAt=op.expiresAt,error="连接已失效，请取消或重新授权后刷新"))
        return {"items":items,"nextCursor":rows[49].id if len(rows)>50 else None}
    if path=="/api/agent/operations/confirm-batch":auth.limit(request);return operations.confirm_batch(s,r,body)
    if path=="/api/agent/operations/{id}":
        if request.method=="GET":return operations.preview(s,r.userId,p["id"])
        auth.limit(request)
        if not isinstance(body,dict) or set(body)!={"approve"} or type(body["approve"]) is not bool:fail("确认参数无效")
        return operations.confirm(s,r,p["id"],body["approve"])
    return NotImplemented
