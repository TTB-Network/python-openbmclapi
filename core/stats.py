from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3
from typing import Any, Optional

from core.utils import (
    FileDataInputStream,
    FileDataOutputStream,
    get_timestamp_from_day_tohour,
    get_timestamp_from_hour_tohour,
)
from core.timer import Timer  # type: ignore


@dataclass
class Counters:
    hit: int = 0
    bytes: int = 0
    qps: int = 0
    sync_bytes: int = 0
    sync_hit: int = 0


cache: Path = Path("./cache")
cache.mkdir(exist_ok=True, parents=True)
caches: dict[int, Counters] = {}
exists_time: list[int] = []
db: sqlite3.Connection = sqlite3.Connection("./cache/stats.db")
db.execute(
    "create table if not exists `Stats`(Time numeric not null, hits numeric default 0, bytes numeric default 0, qps numeric default 0, sync_hits numeric default 0, sync_bytes numeric default 0)"
)
db.commit()


def get_hour(hour: int) -> int:
    return int(get_timestamp_from_hour_tohour(hour))


def get_counter(cur: Optional[int] = None):
    global caches
    cur = cur or get_hour(0)
    if cur not in caches:
        caches[cur] = Counters()
    return caches[cur]


def write():
    global caches
    with open("./cache/stats_count.bin", "wb") as w:
        f = FileDataOutputStream(w)
        for t, v in caches.items():
            f.writeVarInt(t)
            f.writeVarInt(v.hit)
            f.writeVarInt(v.bytes)
            f.writeVarInt(v.qps)
            f.writeVarInt(v.sync_hit)
            f.writeVarInt(v.sync_bytes)


def read():
    global caches
    if not Path("./cache/stats_count.bin").exists():
        return
    with open("./cache/stats_count.bin", "rb") as r:
        f = FileDataInputStream(r)
        while 1:
            try:
                t, h, b, q, sh, sb = (
                    f.readVarInt(),
                    f.readVarInt(),
                    f.readVarInt(),
                    f.readVarInt(),
                    f.readVarInt(),
                    f.readVarInt(),
                )
                if h == b == q == sh == sb == 0:
                    continue
                caches[t] = Counters(h, b, q, sb, sh)
            except:
                break


def execute(cmd: str, *params) -> None:
    global db
    db.execute(cmd, params)
    db.commit()


def executemany(*cmds: tuple[str, tuple[Any, ...]]) -> None:
    global db
    for cmd in cmds:
        db.execute(*cmd)
    db.commit()


def query(cmd: str, *params) -> list[Any]:
    global db
    cur = db.execute(cmd, params)
    return cur.fetchone() or []


def queryAllData(cmd: str, *params) -> list[tuple]:
    global db
    cur = db.execute(cmd, params)
    return cur.fetchall() or []


def exists(cmd: str, *params) -> bool:
    return len(query(cmd, *params)) != 0


def columns(table):
    return [q[0] for q in queryAllData(f"SHOW COLUMNS FROM {table}")]


def addColumns(table, params, data, default=None):
    if params not in columns(table):
        execute(f"ALTER TABLE {table} ADD COLUMN {params} {data}")
        if default is not None:
            execute(f"UPDATE {table} SET {params}={default}")


def write_database():
    global caches, exists_time
    cmds = []
    cur = get_hour(0)
    pops = []
    for t, v in caches.items():
        if t not in exists_time:
            exists_time.append(t)
            if not exists("select `Time` from `Stats` where `Time` = ?", t):
                execute("insert into `Stats`(`Time`) values (?)", t)
        cmds.append(
            (
                "update `Stats` set `hits` = ?, `bytes` = ?, `qps` = ?, `sync_hits` = ?, `sync_bytes` = ? where `Time` = ?",
                (v.hit, v.bytes, v.qps, v.sync_hit, v.sync_bytes, t),
            )
        )
        if t < cur and v.sync_bytes == v.bytes and v.sync_hit == v.sync_hit:
            pops.append(t)
    executemany(*cmds)
    for p in pops:
        caches.pop(p)


read()
Timer.repeat(write, (), 0.01, 0.1)
Timer.repeat(write_database, (), 0.01, 0.1)


def hourly():
    t = get_timestamp_from_day_tohour(0)
    data = []
    for r in queryAllData(
        "select `Time`, `hits`, `bytes`, `qps`, `sync_hits`, `sync_bytes` from `Stats` where `Time` >= ?",
        t,
    ):
        hour = r[0] - t
        data.append(
            {
                "_hour": int(hour),
                "hits": r[1],
                "bytes": r[2],
                "qps": r[3],
                "sync_hit": r[4],
                "sync_bytes": r[5],
            }
        )
    return data


def days():
    t = get_timestamp_from_day_tohour(30)
    data = []
    days: dict[int, Counters] = {}
    for r in queryAllData(
        "select `Time`, `hits`, `bytes`, `qps`, `sync_hits`, `sync_bytes` from `Stats` where `Time` >= ?",
        t,
    ):
        hour = (r[0] - t) // 24
        if hour not in days:
            days[hour] = Counters()
        days[hour].hit += r[1]
        days[hour].bytes += r[2]
        days[hour].qps += r[3]
        days[hour].sync_hit += r[4]
        days[hour].sync_bytes += r[5]
    for day in sorted(days.keys()):
        data.append({"_day": int(day), **asdict(days[day])})
    return data
