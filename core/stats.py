from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3
import time
from typing import Any

from core.utils import (
    DataInputStream,
    DataOutputStream,
    FileDataInputStream,
    FileDataOutputStream,
    get_timestamp_from_day_tohour,
    get_timestamp_from_hour_tohour,
)
from core.api import File
from core.timer import Timer


class StorageStats:
    def __init__(self, name) -> None:
        self._name = name
        self.reset()

    def hit(self, file: File, offset: int):
        byte = file.size - offset
        if file.cache:
            self._cache_hits += 1
            self._cache_bytes += byte
        else:
            self._hits += 1
            self._bytes += byte
        write_storage()

    def failed(self):
        self._failed += 1

    def __str__(self) -> str:
        return "StorageStats(name={}, hits={}, bytes={}, cache_hits={}, cache_bytes={}, total_hits={}, total_bytes={}, failed={}, last_hits={}, last_bytes={})".format(
            self._name,
            self._hits,
            self._bytes,
            self._cache_hits,
            self._cache_bytes,
            self.get_total_hits(),
            self.get_total_bytes(),
            self._failed,
            self._last_hits,
            self._last_bytes,
        )

    def __repr__(self) -> str:
        return self.__str__()

    def get_total_hits(self):
        return self._hits + self._cache_hits

    def get_total_bytes(self):
        return self._bytes + self._cache_bytes

    def get_name(self):
        return self._name

    def reset(self):
        self._hits = 0
        self._bytes = 0
        self._cache_hits = 0
        self._cache_bytes = 0
        self._failed = 0
        self._last_hits = 0
        self._last_bytes = 0

    def get_last_hits(self):
        return self._last_hits

    def get_last_bytes(self):
        return self._last_bytes

    def add_last_hits(self, hits):
        self._last_hits += hits

    def add_last_bytes(self, bytes):
        self._last_bytes += bytes


@dataclass
class SyncStorage:
    sync_hits: int
    sync_bytes: int
    object: StorageStats


storages: dict[str, StorageStats] = {}
cache: Path = Path("./cache")
cache.mkdir(exist_ok=True, parents=True)
last_storages: dict[str, int] = {}
last_hour: int = 0
db: sqlite3.Connection = sqlite3.Connection("./cache/stats.db", check_same_thread=False)
db.execute(
    """
CREATE TABLE IF NOT EXISTS access_logs (  
    id INTEGER PRIMARY KEY AUTOINCREMENT,  
    storage TEXT NOT NULL,  
    hour INTEGER NOT NULL,
    hit INTEGER NOT NULL DEFAULT 0,
    bytes INTEGER NOT NULL DEFAULT 0,
    cache_hit INTEGER NOT NULL DEFAULT 0,
    cache_bytes INTEGER NOT NULL DEFAULT 0,
    last_hit INTEGER NOT NULL DEFAULT 0,
    last_bytes INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0
);"""
)
db.commit()


def read_storage():
    global storages, last_hour
    if (
        not Path("./cache/storage.bin").exists()
        or Path("./cache/storage.bin").stat().st_size == 0
    ):
        return
    with open("./cache/storage.bin", "rb") as r:
        f = FileDataInputStream(r)
        last_hour = f.readVarInt()
        for _ in range(f.readVarInt()):
            storage = StorageStats(f.readString())
            (
                storage._hits,
                storage._bytes,
                storage._cache_hits,
                storage._cache_bytes,
                storage._failed,
                storage._last_hits,
                storage._last_bytes,
            ) = (
                f.readVarInt(),
                f.readVarInt(),
                f.readVarInt(),
                f.readVarInt(),
                f.readVarInt(),
                f.readVarInt(),
                f.readVarInt(),
            )

            storages[storage.get_name()] = storage


def write_storage():
    global storages
    f = DataOutputStream()
    f.writeVarInt(last_hour)
    f.writeVarInt(len(storages))
    for storage in storages.values():
        f.writeString(storage.get_name())
        for field in (
            storage._hits,
            storage._bytes,
            storage._cache_hits,
            storage._cache_bytes,
            storage._failed,
            storage._last_hits,
            storage._last_bytes,
        ):
            f.writeVarInt(field)
    with open("./cache/storage.bin", "wb") as w:
        w.write(f.io.getbuffer())


def get_storage(name):
    global storages
    if name not in storages:
        storages[name] = StorageStats(name)
    return storages[name]


def _write_database():
    global last_storages, last_hour
    cmds: list[tuple[str, tuple[Any, ...]]] = []
    hour = get_hour(0)
    for storage in storages.values():
        if hour not in last_storages or hour != last_storages[storage.get_name()]:
            if not exists(
                "select storage from access_logs where storage = ? and hour = ?",
                storage.get_name(),
                hour,
            ):
                cmds.append(
                    (
                        "insert into access_logs(storage, hour) values (?, ?)",
                        (storage.get_name(), hour),
                    )
                )
            last_storages[storage.get_name()] = hour
        cmds.append(
            (
                "update access_logs set hit = ?, bytes = ?, cache_hit = ?, cache_bytes = ?, last_hit = ?, last_bytes = ?, failed = ? where storage = ? and hour = ?",
                (
                    storage._hits,
                    storage._bytes,
                    storage._cache_hits,
                    storage._cache_bytes,
                    storage._last_hits,
                    storage._last_bytes,
                    storage._failed,
                    storage.get_name(),
                    hour,
                ),
            )
        )
    executemany(*cmds)
    if last_hour and last_hour != hour:
        for storage in storages.values():
            storage.reset()
    last_hour = hour


def get_hour(hour: int) -> int:
    return int(get_timestamp_from_hour_tohour(hour))


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


def hourly():
    data = []
    t = get_timestamp_from_day_tohour(0)
    for r in queryAllData(
        "select storage, hour, hit, bytes, cache_hit, cache_bytes, last_hit, last_bytes, failed from access_logs where hour >= ?",
        t,
    ):
        data.append(
            {
                "_hour": int(r[1] - t),
                "cache_hits": r[4],
                "cache_bytes": r[5],
                "hits": r[2],
                "bytes": r[3],
                "last_hits": r[6],
                "last_bytes": r[7],
                "failed": r[8],
            }
        )
    return data


def daily():
    data = []
    t = get_timestamp_from_day_tohour(30)
    days: dict[int, StorageStats] = {}
    for r in queryAllData(
        "select storage, hour, hit, bytes, cache_hit, cache_bytes, last_hit, last_bytes, failed from access_logs where hour >= ?",
        t,
    ):
        hour = (r[1] - t) // 24
        if hour not in days:
            days[hour] = StorageStats("Total")
        days[hour]._hits += r[2]
        days[hour]._bytes += r[3]
        days[hour]._cache_hits += r[4]
        days[hour]._cache_bytes += r[5]
        days[hour]._last_hits += r[6]
        days[hour]._last_bytes += r[7]
        days[hour]._failed += r[8]
    for day in sorted(days.keys()):
        data.append(
            {
                "_day": int(day),
                "hits": days[day]._hits,
                "bytes": days[day]._bytes,
                "cache_hits": days[day]._cache_hits,
                "cache_bytes": days[day]._cache_bytes,
                "last_hits": days[day]._last_hits,
                "last_bytes": days[day]._last_bytes,
                "failed": days[day]._failed,
            }
        )
    return data


read_storage()
_write_database()


def init():
    Timer.delay(write_database, (), time.time() % 1)


def write_database():
    while 1:
        _write_database()
        time.sleep(1)
