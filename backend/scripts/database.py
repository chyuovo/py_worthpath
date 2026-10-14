"""当前模型结构检查、一致性备份与仅限空库的恢复工具。"""

import argparse
import gzip
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect

from app.config import ROOT
from app.database import engine


def check():
    # 按当前模型和已执行的 Alembic 版本检查，不再对照旧项目冻结结构。
    # command.check 只生成内存中的结构差异，不执行 DDL，也不写入版本号。
    from alembic.config import Config

    from alembic import command

    command.check(Config(str(ROOT / "alembic.ini")))


def backup():
    folder = ROOT / "backups"
    folder.mkdir(exist_ok=True)
    target = folder / (datetime.now().strftime("%Y%m%d-%H%M%S") + ".sql.gz")
    counts = {}
    h = hashlib.sha256()
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as c:
        c.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT")
        names = inspect(c).get_table_names()
        driver = c.connection.driver_connection
        with gzip.open(target, "wt", encoding="utf8", newline="\n") as out:

            def write(s):
                out.write(s)
                h.update(s.encode("utf8"))

            write("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n")
            for table in names:
                q = engine.dialect.identifier_preparer.quote(table)
                ddl = c.exec_driver_sql("SHOW CREATE TABLE " + q).one()[1]
                write(ddl + ";\n")
                count = 0
                for batch in c.exec_driver_sql("SELECT * FROM " + q).partitions(500):
                    for row in batch:
                        literal = ",".join(driver.escape(value) for value in row)
                        write("INSERT INTO " + q + " VALUES (" + literal + ");\n")
                        count += 1
                counts[table] = count
            write("SET FOREIGN_KEY_CHECKS=1;\n")
        c.rollback()
    manifest = {
        "file": target.name,
        "sha256": h.hexdigest(),
        "counts": counts,
        "tables": len(counts),
    }
    target.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf8"
    )
    verify(target)
    return target


def verify(path):
    manifest = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf8"))
    h = hashlib.sha256()
    counts = {}
    creates = 0
    with gzip.open(path, "rt", encoding="utf8", newline="") as f:
        for line in f:
            h.update(line.encode("utf8"))
            if line.startswith("CREATE TABLE "):
                creates += 1
            if line.startswith("INSERT INTO "):
                table = (
                    re.match(r"INSERT INTO (\x60[^\x60]+\x60|\w+) VALUES ", line)
                    .group(1)
                    .strip(chr(96))
                )
                counts[table] = counts.get(table, 0) + 1
    if h.hexdigest() != manifest["sha256"]:
        raise RuntimeError("Backup digest mismatch")
    if creates != manifest["tables"]:
        raise RuntimeError("Backup schema count mismatch")
    if any(counts.get(k, 0) != v for k, v in manifest["counts"].items()):
        raise RuntimeError("Backup row counts mismatch")
    print(
        "Backup gzip, digest, CREATE statements and per-table INSERT counts verified. Restore into a separate empty MySQL is still a distinct manual recovery check."
    )


# 恢复只允许空库，绝不 DROP、TRUNCATE 或覆盖现有业务表。
def restore_empty(path):
    verify(path)
    manifest = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf8"))
    with engine.connect() as connection:
        if inspect(connection).get_table_names():
            raise RuntimeError("Restore requires an explicitly prepared empty database")
        statement = []
        with gzip.open(path, "rt", encoding="utf8") as source:
            for line in source:
                statement.append(line)
                if line.rstrip().endswith(";"):
                    connection.exec_driver_sql("".join(statement))
                    statement = []
        if any(part.strip() for part in statement):
            raise RuntimeError("Incomplete SQL statement")
        connection.commit()
        for table, expected in manifest["counts"].items():
            q = connection.dialect.identifier_preparer.quote(table)
            if (
                connection.exec_driver_sql("SELECT COUNT(*) FROM " + q).scalar()
                != expected
            ):
                raise RuntimeError("Restored row count mismatch")
    print(
        "Restore completed and per-table row counts verified. No existing tables were overwritten."
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["check", "backup", "verify", "restore-empty"])
    p.add_argument("path", nargs="?")
    args = p.parse_args()
    try:
        if args.action == "check":
            check()
        elif args.action == "backup":
            print("Backup created:", backup().name)
        elif args.action == "verify":
            verify(Path(args.path))
        elif args.action == "restore-empty":
            restore_empty(Path(args.path))
    except Exception as e:  # noqa: BLE001 -- 错误信息脱敏，避免泄露数据库凭据。
        print("Database operation failed:", type(e).__name__)
        raise SystemExit(1)
