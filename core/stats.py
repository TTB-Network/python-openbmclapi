from collections import defaultdict
from dataclasses import dataclass
import datetime
from enum import Enum
from pathlib import Path
import sqlite3
import time
import traceback
from typing import Any, Optional
import pyzstd as zstd
from tqdm import tqdm

from core.timings import timing
from core.utils import (
    DataInputStream,
    DataOutputStream,
    FileDataInputStream,
    format_date,
    format_datetime,
    get_timestamp_from_day_today,
    get_timestamp_from_day_tohour,
    get_timestamp_from_hour_tohour,
)
from core.api import File
from core.logger import logger
from core import scheduler
import core.location as location


class UserAgent(Enum):
    OPENBMCLAPI_CLUSTER = "openbmclapi-cluster"
    PYTHON = "python-openbmclapi"
    PHP = "PHP-OpenBmclApi"
    WARDEN = "bmclapi-warden"
    POJAV = "PojavLauncher"
    DALVIK = "Dalvik"
    BAKAXL = "BakaXL"
    OTHER = "Other"
    HMCL = "HMCL"
    PCL2 = "PCL2"
    PCL = "PCL"
    FCL = "FCL"
    GOT = "got"

    @staticmethod
    def parse_ua(user_gent: str) -> list["UserAgent"]:
        data = []
        for ua in user_gent.split(" ") or (user_gent,):
            ua = (ua.split("/") or (ua,))[0].strip().lower()
            for UA in UserAgent:
                if UA.value.lower() == ua:
                    data.append(UA)
        return data or [UserAgent.OTHER]

    @staticmethod
    def get_ua(ua: str) -> "UserAgent":
        for _ in UserAgent:
            if _.value == ua:
                return _
        return UserAgent.OTHER


class GlobalStats:
    def __init__(
        self,
        ua: defaultdict["UserAgent", int] = defaultdict(int),
        ip: defaultdict[str, int] = defaultdict(int),
    ):
        self.useragent: defaultdict["UserAgent", int] = ua
        self.ip: defaultdict[str, int] = ip

    def add_ua(self, ua: str = ""):
        for ua in UserAgent.parse_ua(ua):
            self.useragent[ua] += 1

    def add_ip(self, ip: str):
        self.ip[ip] += 1

    def get_binary(self):
        cache_ip = self.ip.copy()
        cache_ua = self.useragent.copy()
        buf = DataOutputStream()
        buf.writeVarInt(len(cache_ip))
        buf.writeVarInt(len(cache_ua))
        for ip, c in cache_ip.items():
            buf.writeString(ip)
            buf.writeVarInt(c)
        for ua, c in cache_ua.items():
            buf.writeString(ua.value)
            buf.writeVarInt(c)
        return zstd.compress(buf.io.getvalue())

    @staticmethod
    def from_binary(data: bytes):
        input = DataInputStream(zstd.decompress(data))
        ip_length = input.readVarInt()
        ua_length = input.readVarInt()
        cache_ip = {input.readString(): input.readVarInt() for _ in range(ip_length)}
        cache_ua = {
            UserAgent.get_ua(input.readString()): input.readVarInt()
            for _ in range(ua_length)
        }
        return GlobalStats(
            GlobalStats.convert_dict_to_defaultdict(cache_ua, int),
            GlobalStats.convert_dict_to_defaultdict(cache_ip, int),
        )

    @staticmethod
    def convert_dict_to_defaultdict(origin: dict, type: type):
        data = defaultdict(type)
        for k, v in origin.items():
            data[k] = v
        return data

    def reset(self):
        self.useragent.clear()
        self.ip.clear()

    def reset_ua(self):
        self.useragent.clear()

    def reset_ip(self):
        self.ip.clear()


class StorageStats:
    def __init__(self, name) -> None:
        self._name = name
        self.reset()

    def hit(self, file: File, offset: int, ip: str, ua: str = ""):
        global globalStats
        byte = file.size - offset
        if file.cache:
            self._cache_hits += 1
            self._cache_bytes += byte
        else:
            self._hits += 1
            self._bytes += byte
        globalStats.add_ip(ip)
        globalStats.add_ua(ua)
        write_cache()

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


@dataclass
class GEOInfo:
    country: str = ""
    province: str = ""
    value: int = 0

globalStats = GlobalStats()
storages: dict[str, StorageStats] = {}
data: Path = Path("./data")
data.mkdir(exist_ok=True, parents=True)
cache: Path = Path("./data/stats.bin")
db: sqlite3.Connection = sqlite3.Connection("./data/stats.db", check_same_thread=False)
last_hour: Optional[int] = None
last_ip: int = 0
last_ua: int = 0
last_storages: dict[str, int] = {}

def read_cache():
    global last_hour, globalStats
    if not cache.exists():
        return
    with open(cache, "rb") as r:
        try:
            input = FileDataInputStream(r)
            last_hour = input.readVarInt()
            for _ in range(input.readVarInt()):
                storage_data = DataInputStream(zstd.decompress(input.readBytes(input.readVarInt())))
                storage = StorageStats(storage_data.readString())
                (
                    storage._hits,
                    storage._bytes,
                    storage._cache_hits,
                    storage._cache_bytes,
                    storage._failed,
                    storage._last_hits,
                    storage._last_bytes,
                ) = (
                    storage_data.readVarInt(),
                    storage_data.readVarInt(),
                    storage_data.readVarInt(),
                    storage_data.readVarInt(),
                    storage_data.readVarInt(),
                    storage_data.readVarInt(),
                    storage_data.readVarInt(),
                )
                storages[storage.get_name()] = storage
            globalStats = GlobalStats.from_binary(input.readBytes(input.readVarInt()))
        except:
            logger.terror("stats.error.bad")

def write_cache():
    data = DataOutputStream()
    data.writeVarInt(last_hour)
    data.writeVarInt(len(storages))
    for storage in storages.values():
        f = DataOutputStream()
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
        compress = zstd.compress(f.io.getbuffer())
        data.writeVarInt(len(compress))
        data.write(compress)
    binary = globalStats.get_binary()
    data.writeVarInt(len(binary))
    data.write(binary)
    with open(cache, "wb") as w:
        w.write(data.io.getvalue())

def init():
    read_cache()
    execute("create table if not exists access_storage(hour unsigned bigint NOT NULL, storage TEXT NOT NULL, hit unsigned bigint NOT NULL DEFAULT 0, bytes unsigned bigint NOT NULL DEFAULT 0, cache_hit unsigned bigint NOT NULL DEFAULT 0, cache_bytes unsigned bigint NOT NULL DEFAULT 0, last_hit unsigned bigint NOT NULL DEFAULT 0, last_bytes unsigned bigint NOT NULL DEFAULT 0, failed unsigned bigint NOT NULL DEFAULT 0)")
    execute("create table if not exists access_ua(hour unsigned bigint NOT NULL)")
    execute("create table if not exists access_ip(hour unsigned bigint NOT NULL, data blob not null)")
    for ua in UserAgent:
        addColumns(
            "access_ua", f"`{ua.value}`", " unsigned bigint NOT NULL DEFAULT 0"
        )
    scheduler.repeat(write_database, interval=1)

def write_database():
    global last_hour, last_ip, last_ua
    hour = last_hour or get_hour(0)
    cmds: list[tuple[str, tuple[Any, ...]]] = []
    # storages
    for storage in storages.values():
        if (storage.get_name() not in last_storages or last_storages[storage.get_name()] != hour) and not exists("select storage from access_storage where hour = ? and storage = ?", hour, storage.get_name()):
            cmds.append(
                (
                    "insert into access_storage(storage, hour) values (?,?)",
                    (
                        storage.get_name(),
                        hour
                    )
                )
            )
            last_storages[storage.get_name()] = hour
        cmds.append(
            (
                "update access_storage set hit = ?, bytes = ?, cache_hit = ?, cache_bytes = ?, last_hit = ?, last_bytes = ?, failed = ? where storage = ? and hour = ?",
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

    # ua
    if last_ua != hour and not exists("select hour from access_ua where hour = ?", hour):
        cmds.append(
            (
                "insert into access_ua(hour) values (?)",
                (
                    hour,
                )
            )
        )
    last_ua = hour
    g_ua = ",".join((f"`{ua.value}` = ?" for ua in UserAgent))
    cmds.append(
        (
            f"update access_ua set {g_ua} where hour = ?",
            (*(globalStats.useragent.get(ua, 0) for ua in UserAgent), hour),
        )
    )
    # ip
    if last_ip != hour and not exists("select hour from access_ip where hour = ?", hour):
        cmds.append(
            (
                "insert into access_ip(hour, data) values (?, ?)",
                (
                    hour,
                    zstd.compress(b'')
                )
            )
        )
    last_ip = hour
    binary = DataOutputStream()
    binary.writeVarInt(len(globalStats.ip))
    for ip, c in globalStats.ip.items():
        binary.writeString(ip)
        binary.writeVarInt(c)
    cmds.append(
        (
            "update access_ip set data = ? where hour = ?",
            (
                zstd.compress(binary.io.getbuffer()),
                hour
            )
        )
    )
    cur_hour = get_hour(0)
    if last_hour != cur_hour:
        for storage in storages.values():
            storage.reset()
        globalStats.reset()
    last_hour = cur_hour
    executemany(*cmds)



def get_offset_storages() -> list[SyncStorage]:
    sync_storages = []
    for storage in storages.values():
        sync_storage = SyncStorage(
            storage.get_total_hits() - storage.get_last_hits(),
            storage.get_total_bytes() - storage.get_last_bytes(),
            storage,
        )
        if sync_storage.sync_hits == 0 and sync_storage.sync_bytes == 0:
            continue
        sync_storages.append(sync_storage)
    return sync_storages


def get_storage(name):
    global storages
    if name not in storages:
        storages[name] = StorageStats(name)
    return storages[name]


def get_hour(hour: int) -> int:
    return int(get_timestamp_from_hour_tohour(hour))


def get_day(day: int) -> int:
    return int(get_timestamp_from_day_today(day))


def execute(cmd: str, *params) -> None:
    global db
    db.execute(cmd, params)
    db.commit()


def executemany(*cmds: tuple[str, tuple[Any, ...]]) -> None:
    global db
    pbar = None
    if len(cmds) >= 512:
        pbar = tqdm(desc="SQL", total=len(cmds), unit_scale=True)
    for cmd in cmds:
        db.execute(*cmd)
        if pbar is not None:
            pbar.update(1)
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
    # if params not in columns(table):
    try:
        execute(f"ALTER TABLE {table} ADD COLUMN {params} {data}")
        if default is not None:
            execute(f"UPDATE {table} SET {params}={default}")
    except:
        ...

def get_utc_offset():
    return -(time.timezone / 3600)

def get_query_day_tohour(day):
    t = int(time.time())
    return (t - ((t + get_utc_offset() * 3600) % 86400) - 86400 * day) / 3600

def get_query_hour_tohour(hour):
    t = int(time.time())
    return int((t - ((t + get_utc_offset() * 3600) % 3600) - 3600 * hour) / 3600)

def hourly():
    data = []
    hours: dict[int, StorageStats] = {}
    t = get_query_day_tohour(0)
    for r in queryAllData(
        "select storage, hour, hit, bytes, cache_hit, cache_bytes, last_hit, last_bytes, failed from access_storage where hour >= ?",
        t,
    ):
        hour = int(r[1] - t)
        if hour not in hours:
            hours[hour] = StorageStats("Total")
        hours[hour]._hits += r[2]
        hours[hour]._bytes += r[3]
        hours[hour]._cache_hits += r[4]
        hours[hour]._cache_bytes += r[5]
        hours[hour]._last_hits += r[6]
        hours[hour]._last_bytes += r[7]
        hours[hour]._failed += r[8]
    for hour in sorted(hours.keys()):
        data.append(
            {
                "_hour": int(hour),
                "hits": hours[hour]._hits,
                "bytes": hours[hour]._bytes,
                "cache_hits": hours[hour]._cache_hits,
                "cache_bytes": hours[hour]._cache_bytes,
                "last_hits": hours[hour]._last_hits,
                "last_bytes": hours[hour]._last_bytes,
                "failed": hours[hour]._failed,
            }
        )
    return data


def daily():
    data = []
    t = get_query_day_tohour(30)
    to_t = get_query_day_tohour(-1)
    days: dict[int, StorageStats] = {}
    for r in queryAllData(
        "select storage, hour, hit, bytes, cache_hit, cache_bytes, last_hit, last_bytes, failed from access_storage where hour >= ? and hour <= ?",
        t,
        to_t
    ):
        hour = (r[1] + get_utc_offset()) // 24
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
                "_day": format_date(day * 86400),
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

def stats_pro(day):
    format_day = (day == 30)
    t = get_query_hour_tohour(0) - (day * 24)
    g_ua = ",".join((f"`{ua.value}`" for ua in UserAgent))
    s_ua: defaultdict[str, int] = defaultdict(int)
    s_ip: dict[int, defaultdict[str, int]] = {}
    file_bytes, file_download = 0, 0
    for q in queryAllData(
        "select sum(bytes + cache_bytes), sum(hit + cache_hit) from access_storage where hour >= ?", 
        t
    ):
        file_bytes += q[0]
        file_download += q[1]
    for q in queryAllData(
        f"select hour, {g_ua} from access_ua where hour >= ?",
        t,
    ):
        for i, ua in enumerate(UserAgent):
            if q[i + 1] == 0:
                continue
            s_ua[ua.value] += q[i + 1]
    for q in queryAllData(
        f"select hour, data from access_ip where hour >= ?",
        t,
    ):
        hour = (q[0] + get_utc_offset()) if not format_day else (q[0] + get_utc_offset()) // 24
        data = DataInputStream(zstd.decompress(q[1]))
        for ip, c in {data.readString(): data.readVarInt() for _ in range(data.readVarInt())}.items():
            if hour not in s_ip:
                s_ip[hour] = defaultdict(int)
            s_ip[hour][ip] += c
    addresses: defaultdict[location.IPInfo, int] = defaultdict(int)
    for ips in s_ip.values():
        for address, count in ips.items():
            addresses[location.query(address)] += count
    return {
        "useragents": {key: value for key, value in s_ua.items() if value},
        "addresses": [
            GEOInfo(info.country, info.province, count)
            for info, count in sorted(addresses.items(), key=lambda x: x[0].country)
        ],
        "distinct_ip": {(format_datetime(hour * 3600) if not format_day else format_date(hour * 86400)): len(ip) for hour, ip in sorted(s_ip.items())},
        "bytes": file_bytes,
        "downloads": file_download
    }
