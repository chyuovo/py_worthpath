# 恢复和清空：所有写入均在单个串行化事务内；只追加新项目，不覆盖旧数据。
from .backup import *
from . import auth


def conflicts(incoming, existing):
    ids = {
        value
        for p in existing["positions"]
        for value in (p["id"], p.get("importedFromId"))
        if value
    }
    if any(
        p["id"] in ids or (p.get("importedFromId") or p["id"]) in ids
        for p in incoming["positions"]
    ):
        fail("包含已有或重复项目，请勿重复导入；首版只支持追加新项目", 409)
    rs = {(v["currency"], v["baseCurrency"], v["date"]): v for v in existing["rates"]}
    for v in incoming["rates"]:
        old = rs.get((v["currency"], v["baseCurrency"], v["date"]))
        if old and dec(old["rate"]) != dec(v["rate"]):
            fail("已有同日汇率与备份冲突，未修改数据", 409)


def preview(s, r, b):
    b = validate(b)
    existing = data(s, r.userId)
    conflicts(b, existing)
    return dict(
        positions=len(b["positions"]),
        revisions=sum(len(p["revisions"]) for p in b["positions"]),
        rates=len(b["rates"]),
        icons=len(b["icons"]),
        transfers=len(b["transfers"]),
        schedules=len(b["schedules"]),
        baseCurrency=b["baseCurrency"],
        currentBaseCurrency=existing["baseCurrency"],
        message="只追加新项目并重建关联，相同汇率保留。不会覆盖已有项目。已有本位币保留，空账户恢复备份本位币和个人设置。确认后以事务导入，备份中的图标恢复为私有，不会自动发布到共享库。",
    )


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def restore(s, r, b):
    b = validate(b)
    s.scalar(select(User).where(User.id == r.userId).with_for_update())
    existing = data(s, r.userId)
    conflicts(b, existing)
    mapping = {}
    revision_mapping = {}
    icon_mapping = {}
    for i in b["icons"]:
        raw = base64.b64decode(i["image"], validate=True)
        persist(i["hash"], raw)
        icon = one(s, Icon, ownerId=r.userId, hash=i["hash"], shared=False)
        if not icon:
            icon = Icon(
                ownerId=r.userId, name=i["name"], hash=i["hash"], shared=False, data=raw
            )
            s.add(icon)
            s.flush()
        icon_mapping[i["id"]] = icon.id
    for source in b["positions"]:
        v = {
            k: value
            for k, value in source.items()
            if k not in ("id", "importedFromId", "revisions", "iconId")
        }
        for k in ("createdAt", "updatedAt"):
            v[k] = utc(v[k])
        p = Position(
            userId=r.userId,
            importedFromId=source.get("importedFromId") or source["id"],
            iconId=icon_mapping.get(source["iconId"]),
            **v,
        )
        s.add(p)
        s.flush()
        mapping[source["id"]] = p.id
        for original in sorted(
            source["revisions"],
            key=lambda x: (x["date"], x["sequence"], x["createdAt"]),
        ):
            v = {
                k: x for k, x in original.items() if k not in ("id", "sequence", "date")
            }
            for k in ("createdAt", "updatedAt"):
                v[k] = utc(v[k])
            rev = Revision(
                positionId=p.id, effectiveDate=business_date(original["date"]), **v
            )
            s.add(rev)
            s.flush()
            revision_mapping[original["id"]] = rev.id
    for q in b["metalPrices"]:
        key = dict(
            userId=r.userId,
            metalType=q["metalType"],
            currency=q["currency"],
            date=date.fromisoformat(q["date"]),
        )
        old = one(s, MetalPrice, **key)
        if old and dec(old.price) != dec(q["price"]):
            fail("已有同日贵金属价格与备份冲突", 409)
        if not old:
            s.add(
                MetalPrice(
                    **key,
                    price=q["price"],
                    source=q["source"],
                    quotedAt=utc(q["quotedAt"]),
                )
            )
    for t in b["transfers"]:
        v = {
            k: x
            for k, x in t.items()
            if k
            not in (
                "id",
                "importedFromId",
                "date",
                "sourceId",
                "targetId",
                "sourceRevisionId",
                "targetRevisionId",
                "createdAt",
            )
        }
        s.add(
            Transfer(
                userId=r.userId,
                importedFromId=t.get("importedFromId") or t["id"],
                sourceId=mapping[t["sourceId"]],
                targetId=mapping[t["targetId"]],
                sourceRevisionId=revision_mapping[t["sourceRevisionId"]],
                targetRevisionId=revision_mapping[t["targetRevisionId"]],
                effectiveDate=business_date(t["date"]),
                createdAt=utc(t["createdAt"]),
                **v,
            )
        )
    for plan in b["schedules"]:
        v = {
            k: x
            for k, x in plan.items()
            if k not in ("id", "importedFromId", "sourceId", "targetId", "nextAt")
        }
        s.add(
            Schedule(
                userId=r.userId,
                importedFromId=plan.get("importedFromId") or plan["id"],
                sourceId=mapping[plan["sourceId"]],
                targetId=mapping.get(plan["targetId"]),
                nextAt=business_date(plan["nextAt"]),
                **v,
            )
        )
    for link in b["links"]:
        s.add(
            PositionLink(
                sourceId=mapping[link["sourceId"]], targetId=mapping[link["targetId"]]
            )
        )
    for v in b["rates"]:
        key = dict(
            userId=r.userId,
            currency=v["currency"],
            baseCurrency=v["baseCurrency"],
            date=date.fromisoformat(v["date"]),
        )
        if not one(s, ExchangeRate, **key):
            s.add(ExchangeRate(**key, rate=v["rate"], source=v["source"]))
    if not existing["positions"] and not existing["rates"]:
        from .settings import update_settings

        update_settings(s, r, {"baseCurrency": b["baseCurrency"], **b["preferences"]})
        s.execute(
            update(Session).where(Session.userId == r.userId).values(revealUntil=None)
        )
    return {"ok": True, "positions": len(b["positions"])}


def dispatch(s, r, request, response, body):
    path = request.scope["route"].path
    if path == "/api/backup":
        b = data(s, r.userId)
        session = s.get(Session, r.sessionId)
        session.backupDigest = fingerprint(b)
        session.backupExpiresAt = now() + timedelta(minutes=10)
        return Response(
            pack(b),
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="worthpath-'
                + b["exportedAt"][:10]
                + '.zip"'
            },
        )
    if path == "/api/backup/clear-status":
        session = s.get(Session, r.sessionId)
        return {
            "ready": bool(
                session.backupDigest
                and session.backupExpiresAt
                and session.backupExpiresAt > now()
            )
        }
    if path == "/api/backup/clear":
        if body != {"confirmation": "确定清空"}:
            fail("清空确认无效")
        s.scalar(select(User).where(User.id == r.userId).with_for_update())
        session = s.get(Session, r.sessionId)
        if (
            not session.backupDigest
            or not session.backupExpiresAt
            or session.backupExpiresAt <= now()
        ):
            fail("请先下载当前账号备份，再进入下一步（10 分钟内有效）")
        if fingerprint(data(s, r.userId)) != session.backupDigest:
            fail("数据已变化，请重新下载备份", 409)
        for model in (Schedule, Position, MetalPrice, ExchangeRate):
            s.execute(delete(model).where(model.userId == r.userId))
        s.execute(delete(Icon).where(Icon.ownerId == r.userId, Icon.shared.is_(False)))
        s.execute(
            update(Session)
            .where(Session.userId == r.userId)
            .values(backupDigest=None, backupExpiresAt=None)
        )
        return {"ok": True}
    if path == "/api/backup/upload":
        payload = body.get("_filePath") or body.get("_file")
        if not payload:
            fail("请选择 ZIP 备份文件")
        b = unpack(payload)
        result = preview(s, r, b)
        for key, entry in list(uploads.items()):
            if entry["expires"] < now() or entry["userId"] == r.userId:
                uploads.pop(key)
                entry["path"].unlink(missing_ok=True)
        token = str(uuid4())
        folder = ROOT / "runtime/imports"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (token + ".zip")
        if isinstance(payload, bytes):
            target.write_bytes(payload)
        else:
            Path(payload).replace(target)
        uploads[token] = dict(
            userId=r.userId,
            sessionId=r.sessionId,
            path=target,
            expires=now() + timedelta(minutes=15),
        )
        return {**result, "token": token}
    if path == "/api/backup/import-file":
        if (
            not isinstance(body, dict)
            or set(body) != {"confirmed", "token"}
            or body["confirmed"] is not True
        ):
            fail("请确认恢复操作")
        entry = uploads.get(body["token"])
        if (
            not entry
            or entry["userId"] != r.userId
            or entry["sessionId"] != r.sessionId
            or entry["expires"] < now()
        ):
            fail("导入预览已失效，请重新选择备份")
        uploads.pop(body["token"])
        try:
            return restore(s, r, unpack(entry["path"]))
        finally:
            entry["path"].unlink(missing_ok=True)
    return NotImplemented
