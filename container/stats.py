
from dataclasses import dataclass, asdict
import os
from pathlib import Path
import sqlite3
import time
from typing import Any

from utils import FileDataInputStream, FileDataOutputStream
from timer import Timer # type: ignore


@dataclass
class Counters:
    hit: int = 0
    bytes: int = 0
    qps: int = 0
    bandwidth: int = 0

cache: Path = Path("./cache")
cache.mkdir(exist_ok=True, parents=True)

db: sqlite3.Connection = sqlite3.Connection("./cache/stats.db")
db.execute("create table if not exists `Stats`(Time numeric not null, hits numeric default 0, bytes numeric default 0, qps numeric default 0, bandwidth numeric default 0)")
db.commit()
counter = Counters()
last_counter = Counters()
last_time: int = 0
def write():
    global counter, last_counter
    with open("./cache/stats_count.bin", "wb") as w:
        f = FileDataOutputStream(w)
        f.writeVarInt(counter.hit)
        f.writeVarInt(counter.bytes)
        f.writeVarInt(counter.qps)
        f.writeVarInt(counter.bandwidth)
        f.writeVarInt(last_counter.hit)
        f.writeVarInt(last_counter.bytes)

def read():
    global counter, last_counter
    if Path("./cache/stats_count.bin").exists():
        with open("./cache/stats_count.bin", "rb") as r:
            hit = 0
            bytes = 0
            qps = 0
            bandwidth = 0
            last_hit = 0
            last_bytes = 0
            try:
                f = FileDataInputStream(r)
                hit += f.readVarInt()
                bytes += f.readVarInt()
                qps += f.readVarInt()
                bandwidth += f.readVarInt()
                last_hit += f.readVarInt()
                last_bytes += f.readVarInt()
                counter.hit += hit
                counter.bytes += bytes
                counter.qps += qps
                counter.bandwidth += bandwidth
                last_counter.hit += last_hit
                last_counter.bytes += last_bytes
            except:
                ...

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
    return [q[0] for q in queryAllData(f'SHOW COLUMNS FROM {table}')]

async def addColumns(table, params, data, default=None):
    if params not in columns(table):
        execute(f'ALTER TABLE {table} ADD COLUMN {params} {data}')
        if default is not None:
            execute(f'UPDATE {table} SET {params}={default}')

def write_database():
    global last_time, counter
    hits = counter.hit
    bytes = counter.bytes
    qps = counter.qps
    bandwidth = counter.bandwidth
    if hits == bytes == qps == bandwidth == 0:
        return
    t = int(time.time() // 3600)
    if last_time != t and not exists("select `Time` from `Stats` where `Time` = ?", t):
        execute("insert into `Stats`(`Time`) values (?)", t)
    executemany(("update `Stats` set `hits` = ?, `bytes` = ?, `qps` = ? where `Time` = ?", (hits, bytes, qps, t)),
                ("update `Stats` set `bandwidth` = ? where `Time` = ? and `bandwidth` < ?", (bandwidth, t, bandwidth)))
    counter.bandwidth = 0
    if last_time != 0 and last_time != t:
        counter.hit = 0
        counter.bytes = 0
        counter.bandwidth = 0
        counter.qps = 0
        last_counter.hit = 0
        last_counter.bytes = 0
    last_time = t

def hourly():
    t = int(time.time() // 86400) * 24
    data = []
    for r in queryAllData("select `Time`, `hits`, `bytes`, `qps`, `bandwidth` from `Stats` where `Time` >= ?", t):
        hour = r[0] - t + int(os.environ["UTC"])
        data.append(
            {"_hour": hour,
             "hits": r[1],
             "bytes": r[2],
             "qps": r[3], 
             "bandwidth": r[4]
            }
        )
    return data

def days():
    t = (int(time.time() // 86400) - 30) * 24
    r = queryAllData("select `Time`, `hits`, `bytes`, `qps`, `bandwidth` from `Stats` where `Time` >= ?", t)
    data = []
    days: dict[int, Counters] = {}
    for r in queryAllData("select `Time`, `hits`, `bytes`, `qps`, `bandwidth` from `Stats` where `Time` >= ?", t):
        hour = (r[0] - t + int(os.environ["UTC"])) // 24
        if hour not in days:
            days[hour] = Counters()
        days[hour].hit += r[1]
        days[hour].bytes += r[2]
        days[hour].qps += r[3]
        days[hour].bandwidth += r[4]
    for day in sorted(days.keys()):
        data.append({
            "_day": day,
            **asdict(days[day])
        })
    return data
Timer.repeat(write, (), 0.01, 0.1)
Timer.repeat(write_database, (), 1, 1)
read()