# 公共行情调度：按日去重；后台任务使用独立事务，不携带用户信息请求第三方。
import threading
from concurrent.futures import ThreadPoolExecutor
from .common import today
from .config import flag
from .database import transaction
from .auth import Context
_lock=threading.Lock()
_attempts={}
_running=set()
_pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix="worthpath-quotes")
def invalidate(user_id,kind="rates"):
    with _lock:_attempts.pop((user_id,kind),None)
def daily(user_id,kind):
    if not flag("WORTHPATH_ENABLE_QUOTES",True):return
    key=(user_id,kind)
    with _lock:
        if _attempts.get(key)==today() or key in _running:return
        _attempts[key]=today();_running.add(key)
    def work():
        try:
            from . import settings,metals
            with transaction() as s:
                (settings.refresh if kind=="rates" else metals.refresh)(s,Context(user_id,"",True))
        except Exception:
            # 具体失败状态由对应模块保存；不覆盖原汇率或已有估值。
            pass
        finally:
            with _lock:_running.discard(key)
    _pool.submit(work)
async def hourly():
    import asyncio
    from sqlalchemy import select
    from .models import User
    while True:
        await asyncio.sleep(3600)
        try:
            with transaction() as s:ids=list(s.scalars(select(User.id)))
            for user_id in ids:
                daily(user_id,"rates");daily(user_id,"metals")
        except Exception:pass
