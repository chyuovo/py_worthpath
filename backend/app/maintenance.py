# 临时文件生命周期：仅处理本应用生成的 UUID ZIP，不触碰用户备份或其他目录。
import asyncio, re, time
from .common import now
from .config import ROOT


def prune(all_active=False):
    from .backup import uploads
    from .agent_files import TICKETS

    for token, entry in list(uploads.items()):
        if all_active or entry["expires"] <= now():
            uploads.pop(token, None)
            entry["path"].unlink(missing_ok=True)
    for token, entry in list(TICKETS.items()):
        if all_active or entry["expiresAt"] <= now():
            TICKETS.pop(token, None)
    folder = ROOT / "runtime/imports"
    if folder.exists():
        for path in folder.glob("*.zip"):
            if (
                re.fullmatch(r"[a-f0-9-]{36}\.zip", path.name)
                and time.time() - path.stat().st_mtime > 15 * 60
            ):
                path.unlink(missing_ok=True)


async def run():
    while True:
        await asyncio.sleep(60)
        prune()
