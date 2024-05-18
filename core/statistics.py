from collections import defaultdict
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from queue import Queue
import sqlite3
import time
import pyzstd as zstd
from typing import Any, Optional

from tqdm import tqdm

from core import scheduler, utils
from core import location
from core.api import File, Storage
from core.location import IPInfo


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

class Status(Enum):
    SUCCESS = "success"
    REDIRECT = "redirect"
    NOTEXISTS = "not_exists"
    ERROR = "error"
    PARTIAL = "partial"

@dataclass
class GEOInfo:
    country: str = ""
    province: str = ""
    value: int = 0

@dataclass
class StatsStorage:
    hits: int = 0
    bytes: int = 0
    cache_hits: int = 0
    cache_bytes: int = 0
    last_hits: int = 0
    last_bytes: int = 0
    success: int = 0
    redirect: int = 0
    not_exists: int = 0
    error: int = 0
    partial: int = 0

@dataclass
class DataStorage:
    hour: int
    name: str
    type: str
    hit: int = 0
    bytes: int = 0
    cache_hit: int = 0
    cache_bytes: int = 0
    sync_hit: int = 0
    sync_bytes: int = 0
    sync_database: bool = False
    def is_sync(self):
        return self.hit + self.cache_hit == self.sync_hit and self.bytes + self.cache_bytes == self.sync_bytes and self.sync_database

@dataclass
class SyncStorage:
    hour: int
    name: str
    type: str
    hit: int
    bytes: int
last_hour: Optional[int] = None
datadir: Path = Path("./data")
datadir.mkdir(exist_ok=True, parents=True)
db = sqlite3.connect("./data/database.db", check_same_thread=False)
queues: Queue[tuple[str, tuple]] = Queue()
storages: dict[str, int] = {}
lock: utils.WaitLock = utils.WaitLock()
running: int = 1
data_storage: defaultdict[int, list[DataStorage]] = defaultdict(list)


def init():
    execute("create table if not exists access_storage(hour unsigned bigint not null, name text not null, type text not null)")
    for field in (
        "hit",
        "bytes",
        "cache_hit",
        "cache_bytes",
        "sync_hit",
        "sync_bytes",
        *(status.value for status in Status)
    ):
        addColumns("access_storage", field, "unsigned bigint not null default 0")

    execute("create table if not exists access_globals(hour unsigned bigint not null, addresses blob not null, useragents bigint not null)")
    for q in queryAllData(f"select hour, name, type, hit, bytes, cache_hit, cache_bytes, sync_hit, sync_bytes FROM access_storage"):
        qhit = q[3] + q[5]
        qbytes = q[4] + q[6]
        if qhit == q[7] and qbytes == q[8]:
            continue
        storage = DataStorage(
            *q
        )
        storage.sync_database = True
        data_storage[q[0]].append(storage)
    scheduler.delay(task,)
    scheduler.repeat(lock.release, interval=1)


def add_execute(cmd: str, *params) -> None:
    global queues
    queues.put((cmd, params))


def get_hour(hour: int):
    t = int(time.time())
    return (t - (t % 3600) - 3600 * hour) // 3600


def get_data_storage():
    global data_storage
    outdate = []
    cur_hour = get_hour(0)
    for hour, value in data_storage.items():
        if all([storage.is_sync() for storage in value]):
            outdate.append(hour)
    if cur_hour in outdate:
        outdate.remove(cur_hour)
    for hour in outdate:
        data_storage.pop(hour)
    return data_storage


def hit(storage: Storage, file: File, length: int, ip: str, ua: str, status: Status):
    global storages, last_hour
    lock.acquire()
    hour = get_hour(0)
    if (storage.get_name() not in storages or storages[storage.get_name()] != hour) and not exists("select hour from access_storage where hour = ? and name = ? and type = ?", 
        hour, storage.get_name(), storage.get_type()
    ):
        add_execute("insert into access_storage(hour, name, type) values (?,?,?)", hour, storage.get_name(), storage.get_type())
    storages[storage.get_name()] = hour
    cur_storage = None
    data_storages = get_data_storage()
    for origin_storage in data_storages[hour]:
        if origin_storage.name == storage.name and origin_storage.type == storage.type:
            cur_storage = origin_storage
    if cur_storage is None:
        cur_storage = DataStorage(
            hour, storage.name, storage.type
        )
        data_storages[hour].append(cur_storage)
    data = ()
    if not file.cache:
        cur_storage.hit += 1
        cur_storage.bytes += length
        data = (1, length, 0, 0)
    else:
        cur_storage.cache_hit += 1
        cur_storage.cache_bytes += length
        data = (0, 0, 1, length)
    add_execute(f"update access_storage set hit = hit + ?, bytes = bytes + ?, cache_hit = cache_hit + ?, cache_bytes = cache_bytes + ?, {status.value} = {status.value} + 1 where hour = ? and name = ? and type = ?", 
        *data, hour, storage.get_name(), storage.get_type()
    )
    cur_storage.sync_database = False
    if last_hour != hour and not exists("select addresses, useragents from access_globals where hour = ?", hour):
        add_execute("insert into access_globals(hour, addresses, useragents) values (?, ?, ?)", hour, b'', b'')
    data_address, data_useragent = query("select addresses, useragents from access_globals where hour = ?", hour) or [b'', b'']
    address: defaultdict[str, int] = defaultdict(int)
    useragent: defaultdict[UserAgent, int] = defaultdict(int)
    if data_address:
        input = utils.DataInputStream(zstd.decompress(data_address))
        for _ in range(input.readVarInt()):
            addr, c = input.readString(), input.readVarInt()
            address[addr] += c
    if data_useragent:
        input = utils.DataInputStream(zstd.decompress(data_useragent))
        for _ in range(input.readVarInt()):
            u, c = input.readString(), input.readVarInt()
            useragent[UserAgent.get_ua(u)] += c
    address[ip] += 1
    for ua in UserAgent.parse_ua(ua):
        useragent[ua] += 1
    
    output_address = utils.DataOutputStream()
    output_address.writeVarInt(len(address))
    for key, value in address.items():
        output_address.writeString(key)
        output_address.writeVarInt(value)

    output_useragent = utils.DataOutputStream()
    output_useragent.writeVarInt(len(useragent))
    for key, value in useragent.items():
        output_useragent.writeString(key.value)
        output_useragent.writeVarInt(value)
    add_execute("update access_globals set addresses = ?, useragents = ? where hour = ?", zstd.compress(output_address.io.getbuffer()), zstd.compress(output_useragent.io.getbuffer()), hour)



def get_sync_storages():
    data = []    
    for storages in get_data_storage().values():
        for storage in storages:
            chit = storage.hit + storage.cache_hit - storage.sync_hit
            cbytes = storage.bytes + storage.cache_bytes - storage.sync_bytes
            if chit == 0 and cbytes == 0:
                continue
            data.append(
                SyncStorage(
                    storage.hour,
                    storage.name,
                    storage.type,
                    chit,
                    cbytes
                )
            )
        
    return data


def sync(storages: list[SyncStorage]):
    data_storages = get_data_storage()
    for storage in storages:
        hour = storage.hour
        cur_storage = None
        for origin_storage in data_storages[hour]:
            if origin_storage.name == storage.name and origin_storage.type == storage.type:
                origin_storage.sync_hit += storage.hit
                origin_storage.sync_bytes += storage.bytes
                origin_storage.sync_database = False
                cur_storage = origin_storage
        if cur_storage is None:
            continue
        add_execute("update access_storage set sync_hit = sync_hit + ?, sync_bytes = sync_bytes + ? where hour = ? and name = ? and type = ?",
            storage.hit, storage.bytes, hour, storage.name, storage.type
        )
        cur_storage.sync_database = True



async def task():
    global running
    while running:
        await lock.wait()
        while not queues.empty() and running:
            cmd, params = queues.get()
            db.execute(cmd, params)
        db.commit()
        lock.acquire()


def exit():
    global running
    running = 0
    while not queues.empty():
        cmd, params = queues.get()
        db.execute(cmd, params)
    db.commit()
    lock.release()

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
    t = get_query_day_tohour(0)
    status = (status.value for status in Status)
    hours: defaultdict[int, StatsStorage] = defaultdict(lambda: StatsStorage())
    for q in queryAllData(f"select hour, hit, bytes, cache_hit, cache_bytes, sync_hit, sync_bytes, {', '.join(status)} from access_storage where hour >= ?", t):
        hour = int(q[0] - t)
        storage             = hours[hour]
        storage.hits        += q[1]
        storage.bytes       += q[2]
        storage.cache_hits  += q[3]
        storage.cache_bytes += q[4]
        storage.last_hits   += q[5]
        storage.last_bytes  += q[6]
        storage.success     += q[7]
        storage.redirect    += q[8]
        storage.not_exists  += q[9]
        storage.error       += q[10]
        storage.partial     += q[11]
    for hour in sorted(hours.keys()):
        data.append(
            {
                "_hour": hour,
                **asdict(hours[hour])
            }
        )
    return data

def daily():
    data = []
    t = get_query_day_tohour(30)
    to_t = get_query_day_tohour(-1)
    status = (status.value for status in Status)
    days: defaultdict[int, StatsStorage] = defaultdict(lambda: StatsStorage())
    for q in queryAllData(f"select hour, hit, bytes, cache_hit, cache_bytes, sync_hit, sync_bytes, {', '.join(status)} from access_storage where hour >= ? and hour <= ?", t, to_t):
        day = (q[0] + get_utc_offset()) // 24
        storage             = days[day]
        storage.hits        += q[1]
        storage.bytes       += q[2]
        storage.cache_hits  += q[3]
        storage.cache_bytes += q[4]
        storage.last_hits   += q[5]
        storage.last_bytes  += q[6]
        storage.success     += q[7]
        storage.redirect    += q[8]
        storage.not_exists  += q[9]
        storage.error       += q[10]
        storage.partial     += q[11]
    for day in sorted(days.keys()):
        data.append(
            {
                "_day": utils.format_date(day * 86400),
                **asdict(days[day])
            }
        )
    return data


def stats_pro(day: int):
    format_day = day == 30
    t = get_query_hour_tohour(0) - (day * 24)
    status_arr = list(status.value for status in Status)
    status: defaultdict[str, int] = defaultdict(int)
    d_address: defaultdict[int, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    d_ip: dict[str, bool] = {}
    d_geo: defaultdict[IPInfo, int] = defaultdict(int)
    d_useragent: defaultdict[UserAgent, int] = defaultdict(int)
    d_hit, d_bytes, d_sync_hit, d_sync_bytes = 0, 0, 0, 0
    for q in queryAllData(f"select sum(hit + cache_hit) as hit, sum(bytes + cache_bytes) as bytes, sync_hit, sync_bytes, {', '.join(status_arr)} from access_storage where hour >= ?", t):
        d_hit += q[0] or 0
        d_bytes += q[1] or 0
        d_sync_hit += q[2] or 0
        d_sync_bytes += q[3] or 0
        for i, status_val in enumerate(status_arr):
            status[status_val] += q[4 + i] or 0
    for q in queryAllData(f"select hour, addresses, useragents from access_globals where hour >= ?", t):
        hour = (q[0] + get_utc_offset()) if not format_day else (q[0] + get_utc_offset()) // 24
        data_address = q[1]
        data_useragent = q[2]
        if data_address:
            input = utils.DataInputStream(zstd.decompress(data_address))
            for _ in range(input.readVarInt()):
                addr, c = input.readString(), input.readVarInt()
                d_address[hour][addr] += c
                d_ip[addr] = True
        if data_useragent:
            input = utils.DataInputStream(zstd.decompress(data_useragent))
            for _ in range(input.readVarInt()):
                u, c = input.readString(), input.readVarInt()
                d_useragent[UserAgent.get_ua(u)] += c
        
    for addr in map(lambda x: x.items(), d_address.values()):
        for address, count in addr:
            d_geo[location.query(address)] += count
    
    return {
        "useragents": {key.value: value for key, value in d_useragent.items() if value},
        "addresses": [
            GEOInfo(info.country, info.province, count)
            for info, count in sorted(d_geo.items(), key=lambda x: x[0].country)
        ],
        "distinct_ip": {
            (
                utils.format_datetime(hour * 3600)
                if not format_day
                else utils.format_date(hour * 86400)
            ): len(ip)
            for hour, ip in sorted(d_address.items())
        },
        "distinct_ip_count": len(d_ip.keys()),
        "status": {k: v for k, v in status.items() if v != 0},
        "bytes": d_bytes,
        "downloads": d_hit,
        "sync_bytes": d_sync_bytes,
        "sync_downloads": d_sync_hit
    }


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
    try:
        execute(f"ALTER TABLE {table} ADD COLUMN {params} {data}")
        if default is not None:
            execute(f"UPDATE {table} SET {params}={default}")
    except:
        ...
