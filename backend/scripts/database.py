"""Read-only schema check; consistent logical backup; guarded baseline adoption."""

import argparse, gzip, hashlib, json, re, sys, runpy
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect, text
from app.database import engine
from app.models import Base
from app.config import ROOT

REVISION = "0001_existing_schema"


def normalize(ddl):
    ddl = re.sub(r" AUTO_INCREMENT=\d+", "", ddl)
    ddl = re.sub(
        r"CREATE TABLE \x60[^\x60]+\x60",
        "CREATE TABLE <TABLE>",
        ddl,
        count=1,
        flags=re.I,
    )
    ddl = re.sub(
        r"`([^`]+)`", lambda match: chr(96) + match.group(1).lower() + chr(96), ddl
    )
    return ddl.replace("\r", "").strip()


def check(connection):
    names = {n.lower(): n for n in inspect(connection).get_table_names()}
    baseline = runpy.run_path(str(ROOT / "alembic/baseline_schema.py"))["SCHEMA"]
    differences = []
    for name, ddl in baseline.items():
        actual = names.get(name.lower())
        if not actual:
            differences.append(name + ": missing")
            continue
        current = connection.exec_driver_sql(
            "SHOW CREATE TABLE " + connection.dialect.identifier_preparer.quote(actual)
        ).one()[1]
        if normalize(current) != normalize(ddl):
            differences.append(name + ": schema differs")
    if differences:
        raise RuntimeError("; ".join(differences))
    print(
        "All 16 business schemas match the frozen baseline, including indexes, defaults and foreign keys."
    )


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


def adopt():
    with engine.connect() as c:
        check(c)
    target = backup()
    with engine.connect() as c:
        check(c)
    from alembic.config import Config
    from alembic import command

    command.stamp(Config(str(ROOT / "alembic.ini")), REVISION)
    print("Stamped explicit baseline after verified backup:", target.name)


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
    p.add_argument(
        "action", choices=["check", "backup", "adopt", "verify", "restore-empty"]
    )
    p.add_argument("path", nargs="?")
    args = p.parse_args()
    try:
        if args.action == "check":
            with engine.connect() as c:
                check(c)
        elif args.action == "backup":
            backup()
        elif args.action == "verify":
            verify(Path(args.path))
        elif args.action == "restore-empty":
            restore_empty(Path(args.path))
        else:
            adopt()
    except Exception as e:
        print("Database operation failed:", type(e).__name__)
        raise SystemExit(1)
