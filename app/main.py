"""FastAPI HTTP entry; business services are also consumed by MCP."""
import os,json,re
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import JSONResponse,Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError,OperationalError
from starlette.middleware.cors import CORSMiddleware
from .config import ROOT,flag
from .database import transaction
from .common import *
from .models import *
from . import auth,portfolio,queries,transfers
app=FastAPI(title="WorthPath",docs_url="/api/docs",openapi_url="/api/openapi.json",redoc_url=None)
origins=[v.strip() for v in os.getenv("WEB_ORIGIN","").split(",")]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
def allowed_origin(origin):
    try:
        from urllib.parse import urlsplit
        u=urlsplit(origin or "")
        if u.scheme not in ("http","https") or u.path or u.query or u.fragment:return False
        return origin in origins or ("*" in origins and flag("NETWORK_ALLOW_WILDCARD_ORIGINS",os.getenv("NODE_ENV")!="production"))
    except ValueError:return False
@app.middleware("http")
async def security(request,call_next):
    hosts=[v.strip().lower() for v in os.getenv("API_ALLOWED_HOSTS","*").split(",")]
    if "*" not in hosts and request.headers.get("host","").lower() not in hosts:return JSONResponse({"message":"请求 Host 不受信任"},403)
    if request.url.path.startswith("/api") and request.method not in ("GET","HEAD","OPTIONS") and not allowed_origin(request.headers.get("origin")):return JSONResponse({"message":"请求来源不受信任"},403)
    response=await call_next(request)
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="SAMEORIGIN"
    response.headers["Referrer-Policy"]="no-referrer"
    if flag("NETWORK_HSTS",os.getenv("NODE_ENV")=="production"):response.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
    return response
@app.exception_handler(HTTPException)
async def http_error(request,e):return JSONResponse({"message":e.detail},e.status_code,headers=e.headers)
async def validation_error(request,e):
    message="；".join(".".join(str(v) for v in err["loc"])+": "+err["msg"].removeprefix("Value error, ") for err in e.errors())
    return JSONResponse({"message":message},400)
app.add_exception_handler(ValidationError,validation_error)
app.add_exception_handler(RequestValidationError,validation_error)
@app.exception_handler(IntegrityError)
async def integrity_error(request,e):return JSONResponse({"message":"数据已存在或已被其他操作更新，请刷新后重试"},409)
@app.exception_handler(Exception)
async def safe_error(request,e):return JSONResponse({"message":"服务暂时不可用，请稍后重试"},500)
def dispatch(s,r,request,response,body):
    p=request.path_params;q=dict(request.query_params);method=request.method;path=request.scope["route"].path
    if path=="/api/health":return {"status":"ok"}
    if path=="/api/auth/register":fail("公开注册已关闭，请联系管理员创建账号",403)
    if path=="/api/auth/login":return auth.login(s,body,request,response)
    if path=="/api/auth/logout":return auth.logout(s,request,response)
    if path=="/api/auth/me":return auth.profile(s,r)
    if path=="/api/auth/credentials":return auth.change_credentials(s,r,body,request,response)
    if path=="/api/auth/reveal":return auth.reveal(s,r,body,request)
    if path=="/api/auth/lock":s.get(Session,r.sessionId).revealUntil=None;return {"ok":True}
    if path=="/api/auth/activity":s.get(Session,r.sessionId).lastActivity=now();return {"ok":True}
    if path=="/api/positions":
        return portfolio.create(s,r,body) if method=="POST" else portfolio.list_positions(s,r,q.get("kind"))
    if path=="/api/positions/{id}":
        if method=="GET":return portfolio.detail(s,r,p["id"])
        if method=="PATCH":return portfolio.edit(s,r,p["id"],body)
        return portfolio.remove(s,r,p["id"],body)
    if path=="/api/history":return queries.history(s,r,q)
    if path=="/api/positions/{id}/history":
        queries.own(s,r,p["id"]);return queries.history(s,r,{**q,"positionId":p["id"]})
    if path=="/api/overview":return portfolio.overview(s,r)
    if path=="/api/trend":return portfolio.trend_data(s,r,q)
    if path=="/api/positions/{id}/inclusion":return portfolio.quick_meta(s,r,p["id"],body)
    if path=="/api/positions/{id}/repayment-mark":return portfolio.quick_meta(s,r,p["id"],body,True)
    if path=="/api/positions/{id}/deletion":return portfolio.deletion(s,r,p["id"])
    if path=="/api/positions/{id}/links":return portfolio.links(s,r,p["id"],body)
    if path=="/api/positions/{id}/revisions":return portfolio.revise(s,r,p["id"],body)
    if path=="/api/positions/{id}/revisions/{revisionId}":
        if method=="PUT":return portfolio.revise(s,r,p["id"],body,p["revisionId"])
        return portfolio.delete_revision(s,r,p["id"],p["revisionId"])
    if path=="/api/transfers":
        return transfers.execute(s,r,body) if method=="POST" else transfers.list_transfers(s,r,q)
    if path=="/api/transfers/revision/{revisionId}":
        t=s.scalar(transfers.visible_transfer(s,r,revision_id=p["revisionId"]))
        if not t:fail("资金往来记录不存在",404)
        return transfers.describe(s,t)
    if path=="/api/transfers/{id}":return transfers.change(s,r,p["id"],body if method=="PUT" else None)
    for module in extensions:
        result=module.dispatch(s,r,request,response,body)
        if result is not NotImplemented:return result
    fail("接口不存在",404)
extensions=[]
def endpoint_factory():
    async def endpoint(request:Request):
        body={}
        if request.method not in ("GET","HEAD","OPTIONS"):
            raw=await request.body()
            if len(raw)>8*1024*1024:fail("文件不能超过 8 MB",413)
            if raw:
                try:body=json.loads(raw)
                except (ValueError,UnicodeDecodeError):fail("JSON 文件或请求格式无效")
        response=JSONResponse(None,status_code=201 if request.method=="POST" else 200)
        for attempt in range(4):
            try:
                with transaction() as s:
                    public=request.url.path in ("/api/health","/api/auth/register","/api/auth/login")
                    r=None if public else auth.context(s,request)
                    value=dispatch(s,r,request,response,body)
                    s.flush()
                    result=serializable(value) if not isinstance(value,Response) else value
                if isinstance(result,Response):return result
                response.body=json.dumps(result,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()
                response.headers["content-length"]=str(len(response.body))
                return response
            except OperationalError as e:
                if getattr(e.orig,"args",[None])[0] not in (1205,1213) or attempt==3:raise
                await __import__("asyncio").sleep(.02*2**attempt)
    return endpoint
inventory=json.loads((ROOT/"docs/migration-inventory.json").read_text(encoding="utf8"))
core={"auth.ts","portfolio.ts","transfers.ts"}
for route in inventory["http"]:
    if Path(route["source"]).name not in core:continue
    path=re.sub(r":(\w+)",r"{\1}",route["path"])
    app.add_api_route(path,endpoint_factory(),methods=[route["method"]],name=route["method"]+" "+path)
