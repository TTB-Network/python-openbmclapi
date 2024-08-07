from collections import defaultdict
from dataclasses import asdict, dataclass
from enum import Enum
from core import database
from pathlib import Path
from queue import Queue
import time
import pyzstd as zstd
from typing import Any, Optional

from core import logger, scheduler, unit, utils
from core import location
from core.api import File, Storage
from core.location import IPInfo

from functools import cache

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
        global g_ua
        return g_ua.get(ua, UserAgent.OTHER)
    
class Status(Enum):
    SUCCESS = "success"
    REDIRECT = "redirect"
    NOTEXISTS = "not_exists"
    ERROR = "error"
    PARTIAL = "partial"
    FORBIDDEN = "forbidden"

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
    forbidden: int = 0

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


@dataclass
class SummaryStorage:
    time: str = ""
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
    forbidden: int = 0

@dataclass
class SummaryBasic:
    bytes: Optional[SummaryStorage] = None
    hit: Optional[SummaryStorage] = None


last_hour: Optional[int] = None
datadir: Path = Path("./data")
datadir.mkdir(exist_ok=True, parents=True)
queues: Queue[tuple[str, tuple]] = Queue()
storages: dict[str, int] = {}
lock: utils.WaitLock = utils.WaitLock()
running: int = 1
data_storage: defaultdict[int, list[DataStorage]] = defaultdict(list)
cache_ua: defaultdict[UserAgent, int] = defaultdict(int)
cache_address: defaultdict[str, int] = defaultdict(int) 
g_ua: dict[str, "UserAgent"] = {}

for _ in UserAgent:
    g_ua[_.value] = _
    
def init():
    global cache_address, cache_ua
    database.execute("create table if not exists access_storage(hour unsigned bigint not null, name text not null, type text not null)")
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

    database.execute("create table if not exists access_globals(hour unsigned bigint not null, addresses blob not null, useragents bigint not null)")
    for q in database.queryAllData(f"select hour, name, type, hit, bytes, cache_hit, cache_bytes, sync_hit, sync_bytes FROM access_storage"):
        qhit = q[3] + q[5]
        qbytes = q[4] + q[6]
        if qhit == q[7] and qbytes == q[8]:
            continue
        storage = DataStorage(
            *q
        )
        storage.sync_database = True
        data_storage[q[0]].append(storage)
    hour = get_hour(0)
    data_address, data_useragent = database.query("select addresses, useragents from access_globals where hour = ?", hour) or [b'', b'']
    if data_address:
        input = utils.DataInputStream(zstd.decompress(data_address))
        for _ in range(input.readVarInt()):
            addr, c = input.readString(), input.readVarInt()
            cache_address[addr] += c
    if data_useragent:
        input = utils.DataInputStream(zstd.decompress(data_useragent))
        for _ in range(input.readVarInt()):
            u, c = input.readString(), input.readVarInt()
            cache_ua[UserAgent.get_ua(u)] += c
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
    global storages, last_hour, cache_ua, cache_address
    lock.acquire()
    hour = get_hour(0)
    if storage is not None:
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
        save_globals(hour)
        cache_address.clear()
        cache_ua.clear()
    cache_address[ip] += 1
    for ua in UserAgent.parse_ua(ua):
        cache_ua[ua] += 1
    last_hour = hour

def save_globals(hour: int):
    global cache_address, cache_ua
    output_address = utils.DataOutputStream()
    output_address.writeVarInt(len(cache_address))
    for key, value in cache_address.items():
        output_address.writeString(key)
        output_address.writeVarInt(value)

    output_useragent = utils.DataOutputStream()
    output_useragent.writeVarInt(len(cache_ua))
    for key, value in cache_ua.items():
        output_useragent.writeString(key.value)
        output_useragent.writeVarInt(value)
    add_execute("update access_globals set addresses = ?, useragents = ? where hour = ?", zstd.compress(output_address.io.getbuffer()), zstd.compress(output_useragent.io.getbuffer()), hour)



def get_sync_storages() -> list[SyncStorage]:
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
    global running, last_hour
    while running:
        await lock.wait()
        save_globals(last_hour or get_hour(0))
        while not queues.empty() and running:
            cmd, params = queues.get()
            database.execute(cmd, *params)
        database.commit()
        lock.acquire()


def exit():
    global running
    running = 0
    save_globals(last_hour or get_hour(0))
    logger.info(f"正在保存 [{unit.format_number(queues.qsize())}] 统计中")
    while not queues.empty():
        cmd, params = queues.get()
        database.execute(cmd, *params)
    database.commit()
    logger.success(f"成功保存统计")
    lock.release()


def get_utc_offset():
    return -(time.timezone / 3600)


def get_query_day_tohour(day):
    t = int(time.time())
    return (t - ((t + get_utc_offset() * 3600) % 86400) - 86400 * day) / 3600


def get_query_hour_tohour(hour):
    t = int(time.time())
    return int((t - ((t + get_utc_offset() * 3600) % 3600) - 3600 * hour) / 3600)


def hourly(storage_name: str):
    t = get_query_day_tohour(0)
    status = (status.value for status in Status)
    hours: defaultdict[int, StatsStorage] = defaultdict(lambda: StatsStorage())
    for q in database.queryAllData(f"select hour, hit, bytes, cache_hit, cache_bytes, sync_hit, sync_bytes, {', '.join(status)} from access_storage where hour >= ? and name = ?", t, storage_name):
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
        storage.forbidden   += q[12]
    return hours


def daily(storage_name: str):
    t = get_query_day_tohour(30)
    to_t = get_query_day_tohour(-1)
    status = (status.value for status in Status)
    days: defaultdict[int, StatsStorage] = defaultdict(lambda: StatsStorage())
    for q in database.queryAllData(f"select hour, hit, bytes, cache_hit, cache_bytes, sync_hit, sync_bytes, {', '.join(status)} from access_storage where hour >= ? and hour <= ? and name = ?", t, to_t, storage_name):
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
        storage.forbidden   += q[12]
    return days


def get_storage_stats(storage_name: Optional[str] = None):
    days: defaultdict[int, StatsStorage] = defaultdict(lambda: StatsStorage())
    hours: defaultdict[int, StatsStorage] = defaultdict(lambda: StatsStorage())
    fields: tuple = tuple(asdict(StatsStorage()).keys())
    queries = (
        (days, daily),
        (hours, hourly)
    )
    storages = [q[0] for q in database.queryAllData("select distinct name from access_storage")]
    def process_data(storage_name):
        for query_data in queries:
            storage, func = query_data
            queried_data = func(storage_name)
            for timestamp in list(queried_data.keys()):
                for field in fields:
                    setattr(storage[timestamp], field, getattr(storage[timestamp], field) + getattr(queried_data[timestamp], field))
    if storage_name is None:
        for storage_name in storages:
            process_data(storage_name)
    else:
        process_data(storage_name)
    return {
        "hourly": [{
            "_hour": hour,
            **asdict(hours[hour])
        } for hour in sorted(hours.keys())],
        "daily": [{
            "_day": utils.format_date(day * 86400),
            **asdict(days[day])
        } for day in sorted(days.keys())],
        "storages": storages
    }

@cache
def process_address(data: bytes):
    input = utils.DataInputStream(zstd.decompress(data))
    return {input.readString(): input.readVarInt() for _ in range(input.readVarInt())}
@cache
def process_ua(data: bytes):
    input = utils.DataInputStream(zstd.decompress(data))
    return {UserAgent.get_ua(input.readString()): input.readVarInt() for _ in range(input.readVarInt())}
    

def geo_pro(day: int):
    format_day = day == 30
    t = get_query_hour_tohour(0) - (day * 24)
    d_address: defaultdict[int, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    d_ip: set[str] = set()
    d_geo: defaultdict[IPInfo, int] = defaultdict(int)
    d_useragent: defaultdict[UserAgent, int] = defaultdict(int)
    stats_t = StatsTiming()
    stats_t.start("globals")
    for q in database.queryAllData(f"select hour, addresses, useragents from access_globals where hour >= ?", t):
        hour = (q[0] + get_utc_offset()) if not format_day else (q[0] + get_utc_offset()) // 24
        data_address = q[1]
        data_useragent = q[2]
        if data_address:
            for addr, c in process_address(data_address).items():
                d_address[hour][addr] += c
                d_ip.add(addr)
        if data_useragent:
            for u, c in process_ua(data_useragent).items():
                d_useragent[u] += c
    stats_t.start("location", "globals")
    for addr in map(lambda x: x.items(), d_address.values()):
        for address, count in addr:
            d_geo[location.query(address)] += count
    stats_t.end("location")
    stats_t.print()
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
        "distinct_ip_count": len(d_ip),
    }


def stats_pro(day: int):
    t = get_query_hour_tohour(0) - (day * 24)
    status_arr = list(status.value for status in Status)
    status: defaultdict[str, int] = defaultdict(int)
    d_hit, d_bytes, d_sync_hit, d_sync_bytes = 0, 0, 0, 0
    stats_t = StatsTiming()
    stats_t.start("storage")
    for q in database.queryAllData(f"select sum(hit + cache_hit) as hit, sum(bytes + cache_bytes) as bytes, sync_hit, sync_bytes, {', '.join((f'sum({arr})' for arr in status_arr))} from access_storage where hour >= ?", t):
        d_hit += q[0] or 0
        d_bytes += q[1] or 0
        d_sync_hit += q[2] or 0
        d_sync_bytes += q[3] or 0
        for i, status_val in enumerate(status_arr):
            status[status_val] += q[4 + i] or 0
    stats_t.end("storage")
    stats_t.print()
    
    return {
        "status": {k: v for k, v in status.items() if v != 0},
        "bytes": d_bytes,
        "downloads": d_hit,
        "sync_bytes": d_sync_bytes,
        "sync_downloads": d_sync_hit
    }


def summary_basic():
    status = (status.value for status in Status)
    hours: defaultdict[int, SummaryStorage] = defaultdict(lambda: SummaryStorage())
    days: defaultdict[int, SummaryStorage] = defaultdict(lambda: SummaryStorage())
    total: StatsStorage = StatsStorage()
    summary_storage: dict[str, SummaryBasic | StatsStorage] = {
        "hour": SummaryBasic(),
        "day": SummaryBasic(),
        "total": total
    }
    for q in database.queryAllData(f"select hour, hit, bytes, cache_hit, cache_bytes, sync_hit, sync_bytes, {', '.join(status)} from access_storage order by hour desc"):
        hour =              q[0]
        day  =              (q[0] + get_utc_offset()) // 24
        for i, attr in enumerate((
            "hits",        
            "bytes",       
            "cache_hits",  
            "cache_bytes", 
            "last_hits",   
            "last_bytes",  
            "success",     
            "redirect",    
            "not_exists",  
            "error",       
            "partial", 
            "forbidden"   
        )):
            for storage in (
                hours[hour],
                days[day]
            ):
                setattr(storage, attr, getattr(storage, attr, 0) + q[i + 1])
            setattr(total, attr, getattr(total, attr, 0) + q[i + 1])
        for type in (
            ("hour", hours[hour], utils.format_datetime(hour * 3600)), 
            ("day", days[day], utils.format_datetime(day * 86400))
        ):
            storage = summary_storage[type[0]]
            data_storage: SummaryStorage = type[1]
            if storage.bytes is None or (storage.bytes.bytes + storage.bytes.cache_bytes) < data_storage.bytes + data_storage.cache_bytes:
                summary_storage[type[0]].bytes = copy_summary_storage(data_storage)
            if storage.hit is None or (storage.hit.hits + storage.hit.cache_hits) < data_storage.hits + data_storage.cache_hits:
                summary_storage[type[0]].hit = copy_summary_storage(data_storage)
            summary_storage[type[0]].bytes.time = type[2]
            summary_storage[type[0]].hit.time = type[2]
    return summary_storage


def copy_summary_storage(origin: SummaryStorage):
    return SummaryStorage(**asdict(origin))



def exists(cmd: str, *params) -> bool:
    return len(database.query(cmd, *params)) != 0


def columns(table):
    return [q[0] for q in database.queryAllData(f"SHOW COLUMNS FROM {table}")]


def addColumns(table, params, data, default=None):
    try:
        database.execute(f"ALTER TABLE {table} ADD COLUMN {params} {data}")
        if default is not None:
            database.execute(f"UPDATE {table} SET {params}={default}")
    except:
        ...


def get_unknown_ip():
    unknown = set()
    for input in (utils.DataInputStream(zstd.decompress(q[0])) for q in database.queryAllData(f"select addresses from access_globals")):
        for _ in range(input.readVarInt()):
            addr, c = input.readString(), input.readVarInt()
            info = location.query(addr)     
            if info.country == "" or (info.country == "CN" and info.province == "") or not info.country.isalpha():
                unknown.add(addr)
    return sorted(unknown)


class StatsTiming:
    def __init__(self) -> None:
        self.init = time.monotonic()
        self.startup = time.time()
        self.starts: dict[str, float] = {}
        self.ends: dict[str, float] = {}
    def start(self, start: str, end: Optional[str] = None):
        t = time.monotonic_ns()
        self.starts[start] = t
        if end is not None:
            self.ends[end] = t 
    def end(self, end: str):
        t = time.monotonic_ns()
        self.ends[end] = t 
    def print(self):
        times = [*self.ends.values(), *self.starts.values()] or [0]
        end_time = max(times)
        start_time = min(times)
        logger.debug(f"{'=' * 16} Stats Timings {'=' * 16}")
        logger.debug(f"Finished stats {(end_time - start_time) / 1000000000.0:.2f}s")
        for name in self.starts.keys():
            st = self.starts[name]
            sd = self.ends.get(name, None)
            if sd is None:
                logger.debug(f"  {name} finished in -s")
            else:
                logger.debug(f"  {name} finished in {(sd - st) / 1000000000.0:.2f}s")
                
        logger.debug(f"{'=' * 16}==============={'=' * 16}")