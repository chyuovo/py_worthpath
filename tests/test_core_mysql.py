"""Real MySQL integration: only UUID-tagged users created here are removed."""
import secrets,uuid
import httpx,pytest
from sqlalchemy import select,delete,func
from app.database import transaction
from app.models import User,Position,Revision,Transfer,Session,AgentGrant
from app.auth import hash_password
from app.common import today
@pytest.fixture
def users():
    created=[];clients=[]
    try:
        for _ in range(2):
            name="py_migration_"+uuid.uuid4().hex[:16];password=secrets.token_urlsafe(24)
            with transaction() as s:
                u=User(username=name,passwordHash=hash_password(password));s.add(u);s.flush();created.append((u.id,name))
            c=httpx.Client(base_url="http://127.0.0.1:3101/api",headers={"Origin":"http://localhost:5173"},timeout=30)
            res=c.post("/auth/login",json={"username":name,"password":password})
            assert res.status_code==201,res.text
            assert c.cookies.get("wp_session")
            clients.append(c)
        yield clients
    finally:
        for c in clients:c.close()
        with transaction() as s:
            for id,name in created:s.execute(delete(User).where(User.id==id,User.username==name))
def make(c,name,amount,side="asset",kind="account",hidden=False):
    res=c.post("/positions",json=dict(name=name,amount=amount,side=side,kind=kind,hidden=hidden,category="credit_card" if side=="liability" and kind=="account" else "other",currency="CNY",date=today()))
    assert res.status_code==201,res.text
    return res.json()["id"]
def test_mysql_core(users):
    a,b=users
    assert a.get("/auth/me").status_code==200
    source=make(a,"migration source","100.12345678")
    target=make(a,"migration card","20","liability")
    hidden=make(a,"migration hidden","88",hidden=True)
    assert b.get("/positions/"+source).status_code==404
    assert a.get("/positions/"+hidden).status_code==404
    assert len(a.get("/positions").json())==2
    v=dict(sourceId=source,targetId=target,amount="10.00000001",received="10.00000001",fee="-0.00000001",date=today(),requestId=str(uuid.uuid4()))
    first=a.post("/transfers",json=v)
    assert first.status_code==201,first.text
    second=a.post("/transfers",json=v)
    assert second.status_code==201 and second.json()==first.json()
    assert a.get("/positions/"+source).json()["amount"]=="90.12345678"
    assert a.get("/positions/"+target).json()["amount"]=="9.99999999"
    conflict=a.post("/transfers",json={**v,"amount":"11","received":"11"})
    assert conflict.status_code==409
    before=a.get("/positions/"+source).json()["amount"]
    bad=a.post("/transfers",json={**v,"requestId":str(uuid.uuid4()),"operation":"collect"})
    assert bad.status_code==400
    assert a.get("/positions/"+source).json()["amount"]==before
    h=a.get("/positions/"+source+"/history?limit=1").json()
    assert len(h["items"])==1 and h["nextCursor"]
    assert a.get("/positions/"+source+"/history",params={"cursor":h["nextCursor"],"limit":1}).json()["items"][0]["reason"]=="initial"
    assert a.get("/overview").json()["net"]=="80.12"
    assert a.delete("/transfers/"+first.json()["id"]).status_code==200
    assert a.get("/positions/"+source).json()["amount"]=="100.12345678"
    assert a.get("/positions/"+target).json()["amount"]=="20"
    assert a.post("/positions",json={"bad":True}).status_code==400
    assert "detail" not in a.post("/positions",json={"bad":True}).json()
def test_csrf_and_readonly(users):
    a,b=users
    assert httpx.post("http://127.0.0.1:3101/api/auth/login",json={}).status_code==403
    id=b.get("/auth/me").json()["id"]
    with transaction() as s:s.get(User,id).role="readonly"
    assert b.post("/positions",json={}).status_code==403
    assert b.get("/positions").status_code==200
