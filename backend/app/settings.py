# 用户设置和公共日汇率：不向外部服务发送用户身份、账户或金额。
from sqlalchemy import select,update
from .models import User,Session,ExchangeRate
from .common import *
from . import auth
from .schemas import money
STATUS={}
def status(user):return STATUS.get(user,dict(state="idle",attemptedAt=None,message="尚未尝试更新"))
def settings(s,r,include_rates=None):
    if include_rates not in (None,"true","false"):fail("汇率参数无效")
    result=auth.profile(s,r,True);result["fxStatus"]=status(r.userId)
    result["rates"]=[{k:getattr(v,k) for k in ("currency","baseCurrency","date","rate","source")} for v in s.scalars(select(ExchangeRate).where(ExchangeRate.userId==r.userId).order_by(ExchangeRate.date.desc(),ExchangeRate.id.desc()).limit(100))] if include_rates=="true" else []
    return result
def update_settings(s,r,body,response=None,request=None):
    allowed={"baseCurrency","hiddenMenus","accountGroupOrder","showNotes","idleMinutes","sessionHours","requireHiddenPassword","overviewCards","includeIndependentAssets"}
    if not isinstance(body,dict) or not body or set(body)-allowed:fail("设置参数无效")
    for key,value in body.items():
        if key=="baseCurrency" and value not in CURRENCIES:fail("币种无效")
        if key in ("showNotes","requireHiddenPassword","includeIndependentAssets") and type(value) is not bool:fail("设置参数无效")
        if key in ("idleMinutes","sessionHours"):
            low,high=(0,1440) if key=="idleMinutes" else (1,720)
            if type(value) is not int or not low<=value<=high:fail("设置参数无效")
        if key in ("hiddenMenus","accountGroupOrder","overviewCards"):
            if key=="accountGroupOrder" and isinstance(value,list):
                value=[x.strip() if isinstance(x,str) else x for x in value];body[key]=value
            maximum=1000 if key=="accountGroupOrder" else 7
            if not isinstance(value,list) or any(not isinstance(x,str) for x in value) or len(value)>maximum or len(set(value))!=len(value):fail("设置列表无效")
            options=DEFAULT_CARDS if key=="overviewCards" else ["overview","account","asset","debt","history","calendar","schedules"]
            if key!="accountGroupOrder" and set(value)-set(options):fail("设置列表无效")
            if key=="accountGroupOrder" and any(len(x.strip())>60 for x in value):fail("分组名称过长")
    u=s.scalar(select(User).where(User.id==r.userId).with_for_update())
    for key,value in body.items():setattr(u,key,",".join(value) if key=="hiddenMenus" else [v.strip() for v in value] if key=="accountGroupOrder" else value)
    if "requireHiddenPassword" in body:s.execute(update(Session).where(Session.userId==r.userId).values(revealUntil=None))
    if "sessionHours" in body:
        expires=now()+timedelta(hours=body["sessionHours"]);s.get(Session,r.sessionId).expiresAt=expires
        if not r.agent and response is not None:auth.cookie(response,request.cookies["wp_session"],expires)
    return {"ok":True}
PUBLIC_RATES="https://api.frankfurter.dev/v2/rates?base=USD&quotes=CNY,HKD,EUR,GBP,JPY,AUD,CAD,CHF,SGD"
def refresh(s,r):
    import httpx,json
    u=s.get(User,r.userId);ps=s.scalars(select(Position.currency).where(Position.userId==r.userId).distinct()).all()
    if all(c==u.baseCurrency for c in ps):
        message="当前没有需要换算的外币项目";STATUS[r.userId]=dict(state="ok",attemptedAt=iso(now()),message=message);return {"message":message}
    try:
        response=httpx.get(PUBLIC_RATES,timeout=12);response.raise_for_status()
        rows=json.loads(response.text,parse_float=str,parse_int=str)
        by={v["quote"]:v for v in rows if v.get("base")=="USD" and v.get("quote") in CURRENCIES}
        data=[]
        for currency in ps:
            if currency==u.baseCurrency:continue
            source=by[currency] if currency!="USD" else None;target=by[u.baseCurrency] if u.baseCurrency!="USD" else None
            if source and target and source["date"]!=target["date"]:raise ValueError()
            day=source["date"] if source else target["date"]
            if day>today():raise ValueError()
            value=fixed(dec(target["rate"] if target else 1)/dec(source["rate"] if source else 1),12);money(value,False,True,12)
            data.append(dict(userId=r.userId,currency=currency,baseCurrency=u.baseCurrency,date=date.fromisoformat(day),rate=value,source="frankfurter"))
        for v in data:
            key={k:v[k] for k in ("userId","currency","baseCurrency","date")};old=one(s,ExchangeRate,**key)
            if not old:s.add(ExchangeRate(**v))
            elif old.source!="manual":old.rate=v["rate"];old.source="frankfurter"
        message="已保存最新可用日汇率；休市日可能沿用上一工作日。同日历史导入汇率已保留。"
        STATUS[r.userId]=dict(state="ok",attemptedAt=iso(now()),message=message)
        return {"message":message}
    except Exception:
        STATUS[r.userId]=dict(state="error",attemptedAt=iso(now()),message="自动汇率更新失败，原币和已有汇率已保留，请稍后重试")
        fail("汇率更新失败，原币金额和已有汇率已保留；可稍后重试或手动录入",502)
from .models import Position
def dispatch(s,r,request,response,body):
    path=request.scope["route"].path
    if path=="/api/settings":return settings(s,r,request.query_params.get("rates")) if request.method=="GET" else update_settings(s,r,body,response,request)
    if path=="/api/rates/refresh":return refresh(s,r)
    return NotImplemented
