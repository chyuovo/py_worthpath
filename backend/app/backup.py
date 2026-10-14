# ZIP v9 备份：仅追加恢复；恢复前校验完整性、关联、配对金额和重复来源。
import base64, hashlib, io, json, zipfile, secrets
from uuid import uuid4, UUID
from pathlib import Path
from sqlalchemy import select, delete, update, or_
from fastapi.responses import Response
from .common import *
from .models import *
from .auth import Context
from .queries import current_positions, rates
from .schemas import PositionInput, RevisionInput, TransferInput, money, check_date
from .calculation import movement_deltas
from .icons import normalize, persist
from .config import ROOT

FILES = [
    "settings.json",
    "currencies.json",
    "accounts.json",
    "assets.json",
    "debts.json",
    "history.json",
    "links.json",
    "rates.json",
    "icons.json",
    "transfers.json",
    "schedules.json",
]
uploads = {}


def data(s, user_id):
    r = Context(user_id, "", True)
    u = s.get(User, user_id)
    ps = current_positions(s, r, all_history=True)
    positions = []
    links = []
    for p in ps:
        p.pop("userId")
        links.extend(
            dict(sourceId=l["sourceId"], targetId=l["targetId"])
            for l in p.pop("outgoing")
        )
        p["revisions"] = [
            dict(
                id=v["id"],
                sequence=v["sequence"],
                amount=decimal_string(v["amount"]),
                date=business_time(v["effectiveDate"]),
                notes=v["notes"],
                reason=v["reason"],
                createdAt=iso(v["createdAt"]),
                updatedAt=iso(v["updatedAt"]),
            )
            for v in p["revisions"]
        ]
        positions.append(p)
    rs = [
        {k: v[k] for k in ("currency", "baseCurrency", "date", "rate", "source")}
        for v in rates(s, r)
    ]
    for v in rs:
        v["date"] = v["date"].isoformat()
    icon_ids = [p["iconId"] for p in ps if p["iconId"]]
    icons = [
        dict(
            id=i.id,
            name=i.name,
            shared=i.shared,
            hash=i.hash,
            image=base64.b64encode(i.data).decode(),
        )
        for i in s.scalars(
            select(Icon).where(or_(Icon.ownerId == user_id, Icon.id.in_(icon_ids)))
        )
    ]
    ts = []
    for t in s.scalars(select(Transfer).where(Transfer.userId == user_id)):
        v = row(t)
        v.pop("userId")
        v["date"] = business_time(v.pop("effectiveDate"))
        ts.append(v)
    plans = []
    for t in s.scalars(select(Schedule).where(Schedule.userId == user_id)):
        v = row(t)
        v.pop("userId")
        v["nextAt"] = business_time(v["nextAt"])
        plans.append(v)
    prices = []
    for t in s.scalars(select(MetalPrice).where(MetalPrice.userId == user_id)):
        v = row(t)
        v.pop("id")
        v.pop("userId")
        v["date"] = v["date"].isoformat()
        prices.append(v)
    preferences = {
        k: getattr(u, k)
        for k in (
            "showNotes",
            "idleMinutes",
            "sessionHours",
            "requireHiddenPassword",
            "includeIndependentAssets",
        )
    }
    preferences.update(
        hiddenMenus=list(filter(None, u.hiddenMenus.split(","))),
        accountGroupOrder=u.accountGroupOrder or [],
        overviewCards=u.overviewCards if u.overviewCards is not None else DEFAULT_CARDS,
    )
    currencies = list(
        dict.fromkeys(
            [u.baseCurrency]
            + [p["currency"] for p in ps]
            + [c for v in rs for c in (v["currency"], v["baseCurrency"])]
        )
    )
    return serializable(
        dict(
            format="worthpath",
            version=9,
            exportedAt=iso(now()),
            baseCurrency=u.baseCurrency,
            preferences=preferences,
            currencies=currencies,
            positions=positions,
            links=links,
            rates=rs,
            icons=icons,
            transfers=ts,
            schedules=plans,
            metalPrices=prices,
        )
    )


def fingerprint(b):
    b = json.loads(json.dumps(b))
    b.pop("exportedAt", None)
    b["positions"].sort(key=lambda p: p["id"])
    for p in b["positions"]:
        p["revisions"].sort(key=lambda v: v["id"])
    b["links"].sort(key=lambda v: v["sourceId"] + v["targetId"])
    b["rates"].sort(key=lambda v: v["currency"] + v["baseCurrency"] + v["date"])
    b["metalPrices"].sort(key=lambda v: v["metalType"] + v["currency"] + v["date"])
    b["currencies"].sort()
    for key in ("icons", "transfers", "schedules"):
        b[key].sort(key=lambda v: v["id"])
    return digest(json.dumps(b, ensure_ascii=False, separators=(",", ":")))


def pack(b):
    metadata = [
        {k: v for k, v in p.items() if k != "revisions"} for p in b["positions"]
    ]
    contents = {
        "settings.json": {
            k: b[k] for k in ("baseCurrency", "preferences", "metalPrices")
        },
        "currencies.json": b["currencies"],
        "history.json": [
            {**v, "positionId": p["id"]} for p in b["positions"] for v in p["revisions"]
        ],
    }
    for name, kind in (
        ("accounts.json", "account"),
        ("assets.json", "asset"),
        ("debts.json", "debt"),
    ):
        contents[name] = [p for p in metadata if p["kind"] == kind]
    for key in ("links", "rates", "icons", "transfers", "schedules"):
        contents[key + ".json"] = b[key]
    raw = {
        name: json.dumps(contents[name], ensure_ascii=False, indent=2).encode()
        for name in FILES
    }
    raw["manifest.json"] = json.dumps(
        dict(
            format="worthpath",
            version=9,
            exportedAt=b["exportedAt"],
            files=[
                dict(name=name, sha256=hashlib.sha256(raw[name]).hexdigest())
                for name in FILES
            ],
        ),
        indent=2,
    ).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, value in raw.items():
            z.writestr(name, value)
    return output.getvalue()


def unpack(payload):
    try:
        with zipfile.ZipFile(
            io.BytesIO(payload) if isinstance(payload, bytes) else payload
        ) as z:
            entries = z.infolist()
            names = [i.filename for i in entries]
            if (
                len(names) != 12
                or set(names) != set(FILES + ["manifest.json"])
                or sum(i.file_size for i in entries) > 1024**3
                or any(i.flag_bits & 1 for i in entries)
            ):
                raise ValueError()
            raw = {n: z.read(n) for n in names}
        manifest = json.loads(raw["manifest.json"])
        if (
            set(manifest) != {"format", "version", "exportedAt", "files"}
            or manifest["format"] != "worthpath"
            or manifest["version"] != 9
        ):
            raise ValueError()
        if len(manifest["files"]) != 11 or {
            x["name"] for x in manifest["files"]
        } != set(FILES):
            raise ValueError()
        for entry in manifest["files"]:
            if hashlib.sha256(raw[entry["name"]]).hexdigest() != entry["sha256"]:
                raise ValueError()
        loaded = {n: json.loads(v.decode("utf8")) for n, v in raw.items()}
        settings = loaded["settings.json"]
        if set(settings) != {"baseCurrency", "preferences", "metalPrices"}:
            raise ValueError()
        ps = []
        for filename, kind in zip(
            ("accounts.json", "assets.json", "debts.json"), ("account", "asset", "debt")
        ):
            for p in loaded[filename]:
                if p["kind"] != kind or "revisions" in p:
                    raise ValueError()
                ps.append(p)
        grouped = {p["id"]: [] for p in ps}
        for rev in loaded["history.json"]:
            position_id = rev.pop("positionId")
            if position_id not in grouped:
                raise ValueError()
            grouped[position_id].append(rev)
        for p in ps:
            p["revisions"] = grouped[p["id"]]
        return dict(
            format="worthpath",
            version=9,
            exportedAt=manifest["exportedAt"],
            **settings,
            currencies=loaded["currencies.json"],
            positions=ps,
            **{
                k: loaded[k + ".json"]
                for k in ("links", "rates", "icons", "transfers", "schedules")
            },
        )
    except Exception:
        fail(
            "备份 ZIP 无效：仅接受当前 v9 格式，不支持旧备份。请检查 JSON 文件、完整性及文件大小（上传 512 MB，解压总计 1 GB；不限制记录条数）"
        )


def _validate(b):
    required = {
        "format",
        "version",
        "exportedAt",
        "baseCurrency",
        "preferences",
        "currencies",
        "positions",
        "links",
        "rates",
        "icons",
        "transfers",
        "schedules",
        "metalPrices",
    }
    if (
        not isinstance(b, dict)
        or set(b) != required
        or b["format"] != "worthpath"
        or b["version"] != 9
    ):
        fail("备份数据必须来自当前 ZIP v9 格式")
    if (
        b["baseCurrency"] not in CURRENCIES
        or b["baseCurrency"] not in b["currencies"]
        or set(b["currencies"]) - set(CURRENCIES)
    ):
        fail("币种清单不完整")
    preferences = b["preferences"]
    preference_keys = {
        "hiddenMenus",
        "accountGroupOrder",
        "sessionHours",
        "requireHiddenPassword",
        "overviewCards",
        "includeIndependentAssets",
        "showNotes",
        "idleMinutes",
    }
    if not isinstance(preferences, dict) or set(preferences) != preference_keys:
        fail("备份个人设置字段不完整")
    for key in ("requireHiddenPassword", "includeIndependentAssets", "showNotes"):
        if type(preferences[key]) is not bool:
            fail("备份设置类型无效")
    for key, low, high in (("sessionHours", 1, 720), ("idleMinutes", 0, 1440)):
        if type(preferences[key]) is not int or not low <= preferences[key] <= high:
            fail("备份设置范围无效")
    for key, maximum, options in (
        (
            "hiddenMenus",
            7,
            [
                "overview",
                "account",
                "asset",
                "debt",
                "history",
                "calendar",
                "schedules",
            ],
        ),
        ("overviewCards", 7, DEFAULT_CARDS),
        ("accountGroupOrder", 1000, None),
    ):
        values = preferences[key]
        if (
            not isinstance(values, list)
            or any(not isinstance(x, str) for x in values)
            or len(values) > maximum
        ):
            fail("备份设置列表无效")
        if key == "accountGroupOrder":
            values = [x.strip() for x in values]
            if any(len(x) > 60 for x in values):
                fail("分组名称过长")
        if len(set(values)) != len(values) or (
            options is not None and set(values) - set(options)
        ):
            fail("备份设置列表无效")
    position_keys = set(Position.__table__.columns.keys()) - {"userId"}
    for position in b["positions"]:
        if set(position) - position_keys - {"revisions"} or (
            position_keys - {"lastRepaymentMonth", "lastBookedDate"}
        ) - set(position):
            fail("备份项目字段不完整")
        for revision in position["revisions"]:
            if set(revision) != {
                "id",
                "sequence",
                "amount",
                "date",
                "notes",
                "reason",
                "createdAt",
                "updatedAt",
            }:
                fail("备份历史字段不完整")
    ids = {p["id"]: p for p in b["positions"]}
    origins = [p.get("importedFromId") or p["id"] for p in b["positions"]]
    if len(ids) != len(b["positions"]) or len(set(origins)) != len(origins):
        fail("备份内包含重复项目")
    revs = {}
    icon_ids = set()
    for icon in b["icons"]:
        UUID(icon["id"])
        if icon["id"] in icon_ids:
            fail("图标关联无效")
        icon_ids.add(icon["id"])
        raw = base64.b64decode(icon["image"], validate=True)
        if (
            base64.b64encode(raw).decode() != icon["image"]
            or hashlib.sha256(raw).hexdigest() != icon["hash"]
        ):
            fail("图标内容或校验值无效")
        normalize(raw)
        from PIL import Image

        image = Image.open(io.BytesIO(raw))
        if image.format != "PNG" or max(image.size) > 256:
            fail("备份图标必须是规范的 PNG")
    for p in b["positions"]:
        UUID(p["id"])
        if p.get("iconId") and p["iconId"] not in icon_ids:
            fail("图标关联无效")
        sample = {
            k: p[k]
            for k in (
                "name",
                "category",
                "groupName",
                "kind",
                "side",
                "currency",
                "notes",
                "archived",
                "hidden",
                "included",
            )
        }
        PositionInput.model_validate(
            {
                **sample,
                "amount": "0",
                "date": p["revisions"][0]["date"] if p["revisions"] else "1900-01-01",
            }
        )
        if p["currency"] not in b["currencies"]:
            fail("币种清单不完整")
        sequences = set()
        for rev in p["revisions"]:
            UUID(rev["id"])
            RevisionInput.model_validate(
                {k: rev[k] for k in ("amount", "date", "notes", "reason")}
            )
            if rev["id"] in revs or rev["sequence"] in sequences:
                fail("重复历史记录")
            if (
                rev["sequence"] <= 0
                or rev["sequence"] > 2147483647
                or len(rev["date"]) != 16
            ):
                fail("历史顺序无效")
            if p["kind"] != "account" and dec(rev["amount"]) < 0:
                fail("仅账户支持负余额")
            sequences.add(rev["sequence"])
            revs[rev["id"]] = (p, rev)
        if p.get("lastRepaymentMonth") and (
            p["kind"] != "account" or p["side"] != "liability"
        ):
            fail("还款月份仅适用于欠款账户")
        if p.get("lastBookedDate") and p["kind"] != "account":
            fail("仅账户支持当天记账标记")
        if (
            p.get("metalType")
            or p.get("metalGrams")
            or p.get("autoValuation")
            or p.get("metalCostPerGram") is not None
        ):
            from .metals import config

            if p["kind"] != "asset" or p["category"] != "gold":
                fail("贵金属估价关联无效")
            config(
                {
                    k: p[k]
                    for k in (
                        "metalType",
                        "metalGrams",
                        "metalCostPerGram",
                        "autoValuation",
                    )
                }
            )
        if not 0 < dec(p["metalPurity"]) <= 1:
            fail("纯度应大于 0 且不超过 1")
    used = set()
    seen = set()
    for t in b["transfers"]:
        TransferInput.model_validate(
            {
                k: t[k]
                for k in (
                    "sourceId",
                    "targetId",
                    "amount",
                    "received",
                    "fee",
                    "operation",
                    "date",
                    "notes",
                )
            }
        )
        source = ids.get(t["sourceId"])
        target = ids.get(t["targetId"])
        origin = t.get("importedFromId") or t["id"]
        if (
            origin in seen
            or not source
            or not target
            or source["kind"] != "account"
            or source["currency"] != t["sourceCurrency"]
            or target["currency"] != t["targetCurrency"]
        ):
            fail("转账关联无效")
        seen.add(origin)
        if t["operation"] == "transfer":
            if target["kind"] != "account":
                fail("转账关联无效")
        elif (
            source["side"] != "asset"
            or target["kind"] != "debt"
            or target["side"]
            != ("liability" if t["operation"] in ("borrow", "repay") else "asset")
        ):
            fail("转账关联无效")
        if source["currency"] == target["currency"] and dec(t["amount"]) != dec(
            t["received"]
        ):
            fail("同币种转账金额不一致")
        sd, td, sr, tr = movement_deltas(
            t["operation"],
            t["amount"],
            t["received"],
            t["fee"],
            source["side"],
            target["side"],
        )
        for p, rid, reason, delta in (
            (source, t["sourceRevisionId"], sr, sd),
            (target, t["targetRevisionId"], tr, td),
        ):
            ordered = sorted(
                p["revisions"], key=lambda x: (x["date"], x["sequence"], x["createdAt"])
            )
            index = next((i for i, v in enumerate(ordered) if v["id"] == rid), -1)
            if rid in used or index < 0:
                fail("转账历史与双方金额不一致")
            v = ordered[index]
            before = dec(ordered[index - 1]["amount"]) if index else dec(0)
            if (
                v["reason"] != reason
                or v["date"] != t["date"]
                or dec(v["amount"]) - before != delta
            ):
                fail("转账历史与双方金额不一致")
            used.add(rid)
    if any(rev["reason"] in PAIRED and id not in used for id, (_, rev) in revs.items()):
        fail("缺少配对转账记录")
    seen = set()
    for link in b["links"]:
        source = ids.get(link["sourceId"])
        target = ids.get(link["targetId"])
        key = (link["sourceId"], link["targetId"])
        if (
            not source
            or not target
            or source["kind"] != "debt"
            or target["kind"] == "debt"
            or key in seen
        ):
            fail("关联关系无效")
        seen.add(key)
    seen = set()
    for v in b["rates"]:
        key = (v["currency"], v["baseCurrency"], v["date"])
        money(v["rate"], False, True, 12)
        check_date(v["date"])
        if (
            key in seen
            or key[0] == key[1]
            or v["source"] not in ("manual", "frankfurter")
        ):
            fail("重复汇率或汇率无效")
        seen.add(key)
    from .schedules import parse

    seen = set()
    for plan in b["schedules"]:
        parse(
            {
                k: plan[k]
                for k in (
                    "name",
                    "operation",
                    "sourceId",
                    "targetId",
                    "amount",
                    "received",
                    "nextAt",
                    "intervalDays",
                    "notes",
                )
            }
        )
        source = ids.get(plan["sourceId"])
        target = ids.get(plan["targetId"])
        origin = plan.get("importedFromId") or plan["id"]
        if (
            origin in seen
            or not source
            or source["kind"] != "account"
            or (
                plan["operation"] == "expense"
                and (source["side"] != "asset" or plan["targetId"])
            )
            or (
                plan["operation"] == "transfer"
                and (
                    not target
                    or target["kind"] != "account"
                    or (
                        source["currency"] == target["currency"]
                        and dec(plan["amount"]) != dec(plan["received"])
                    )
                )
            )
        ):
            fail("计划账户关联无效")
        seen.add(origin)
    return b


def validate(b):
    try:
        return _validate(b)
    except HTTPException:
        raise
    except (KeyError, ValueError, TypeError, AttributeError):
        fail("备份数据字段缺失或格式无效")
