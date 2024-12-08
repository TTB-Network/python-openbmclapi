import asyncio
import base64
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, fields, is_dataclass
import datetime
import io
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from typing import Any, Optional

import aiohttp
import psutil

from core import cluster, config, logger, units
import ipdb
from . import utils

from . import scheduler
from .web import (
    routes as route,
    time_qps
)
from aiohttp import web

from . import database as db

@dataclass
class CollectionUsage:
    total: int
    usage: int

@dataclass
class ConnectionStatistics:
    tcp: int
    udp: int

    @property
    def total(self):
        return self.tcp + self.udp

@dataclass
class ClusterInfo:
    name: str

@dataclass
class SystemInfo:
    cpu_usage: float
    memory_usage: int
    connection: ConnectionStatistics
    clusters: list[str]
    qps: int

@dataclass
class CounterValue:
    _: float
    value: SystemInfo

@dataclass
class CounterQPS:
    _: float
    value: int

@dataclass
class CounterSystemInfo:
    _: float
    cpu: float
    memory: int
    connection: ConnectionStatistics

class Counter:
    def __init__(self, max: int = 1500):
        self._data: deque[CounterValue] = deque(maxlen=max)
        self.max = max
    
    def add(self, value: SystemInfo):
        self._data.append(CounterValue(
            utils.get_runtime(),
            value
        ))
    
    def last(self):
        return self._data[-1] if self._data else None

    def __len__(self):
        return len(self._data)
    
    def get_json(self):
        return [
            {"_": item._,
             "value": {
                 "cpu": item.value.cpu_usage,
                 "memory": item.value.memory_usage,
                 "connection": {
                     "tcp": item.value.connection.tcp,
                     "udp": item.value.connection.udp,
                 },
                 "qps": item.value.qps
             }} for item in self._data
        ]
    
    @property
    def all_qps(self):
        return [
            CounterQPS(
                item._,
                item.value.qps
            ) for item in self._data.copy()
        ]
    
    @property
    def all_system_info(self):
        return [
            CounterSystemInfo(
                item._,
                item.value.cpu_usage,
                item.value.memory_usage,
                item.value.connection
            ) for item in self._data.copy()
        ]

@dataclass
class GithubPath:
    path: str
    size: int
    sha: Optional[str] = None

    def __hash__(self) -> int:
        return hash(self.path)

    @property
    def is_file(self):
        return self.sha is not None

    @property
    def is_dir(self):
        return self.sha is None

    def __repr__(self):
        return f"{self.path} ({self.size})"

@dataclass
class APIQPSConfig:
    count: int = 60
    interval: int = 5

@dataclass
class APIStatistics:
    _: int | str
    bytes: int
    hits: int
    
@dataclass
class APIResponseStatistics:
    _: int | str
    success: int
    partial: int
    forbidden: int
    not_found: int
    error: int
    redirect: int

counter = Counter()
process = psutil.Process(os.getpid())
task: Optional[threading.Thread] = None
running: int = 1
GITHUB_BASEURL = "https://api.github.com"
GITHUB_REPO = "TTB-Network/python-openbmclapi"
UTC = 28800 # UTC + 8 hours (seconds)
IPDB = ipdb.City("./ipipfree.ipdb")
IPDB_CACHE: dict[str, str] = {}

@route.get('/pages')
@route.get("/pages/{tail:.*}")
async def _(request: web.Request):
    return web.FileResponse("./assets/index.html")

@route.get('/')
async def _(request: web.Request):
    return web.FileResponse("./assets/index.html")

@route.get("/favicon.ico")
async def _(request: web.Request):
    return web.FileResponse("./assets/favicon.ico")

@route.get("/assets/js/config.js")
async def _(request: web.Request):
    dashboard_config = json.dumps({
        "version": config.VERSION,
        "api_version": config.API_VERSION,
        "python_version": config.PYTHON_VERSION,
        "support": {
            "websocket": True,
            "polling": True
        },
    })
    content = f'window.__CONFIG__ = {dashboard_config}'
    return web.Response(
        body=content,
        content_type="application/javascript"
    )

@route.get("/api")
async def _(request: web.Request):
    try:
        # if request is websocket, return websocket
        if request.headers.get("upgrade") == "websocket":
            resp = web.WebSocketResponse()
            await resp.prepare(request)
            async for msg in resp:
                data = json.loads(msg.data)
                asyncio.create_task(websocket_process_api(resp, data))
            return resp
        else:
            return web.json_response(await process_api(request.query.get("event", None), None))
    except:
        return web.HTTPException()

@route.post("/api")
async def _(request: web.Request):
    try:
        data = await request.json()
        resp: list[Any] = []
        if not isinstance(data, list):
            data = [data]
        resp = await asyncio.gather(*[process_api(item.get("event"), item.get("data")) for item in data])
        return web.json_response(resp, dumps=json_dumps)
    except:
        return web.json_response([])

@route.get("/api/system_info")
async def _(request: web.Request):
    return web.json_response(counter.get_json())

@route.get("/api/count")
async def _(request: web.Request):
    # statistics of the cluster hits and bytes
    session = db.SESSION.get_session()
    current_hour = db.get_hour()
    hour_of_day = (current_hour // 24) * 24
    next_hour = hour_of_day + 24
    q = session.query(db.ClusterStatisticsTable).filter(
        db.ClusterStatisticsTable.hour >= hour_of_day,
        db.ClusterStatisticsTable.hour < next_hour
    ).all()
    return web.json_response({
        "hits": sum([int(item.hits) for item in q]), # type: ignore
        "bytes": sum([int(item.bytes) for item in q]) # type: ignore
    })
    

@route.get("/api/openbmclapi/rank")
async def _(request: web.Request):
    async with aiohttp.ClientSession(
        "bd.bangbang93.com"
    ) as session:
        async with session.get("/openbmclapi/metric/rank") as resp:
            return web.json_response(
                await resp.json(),
            )

route.static("/assets", "./assets")

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.strftime("%Y-%m-%d %H:%M:%S")
        if is_dataclass(o):
            return asdict(o) # type: ignore
        return super().default(o)

def json_dumps(data: Any, *args, **kwargs) -> str:
    return json.dumps(data, cls=JSONEncoder, *args, **kwargs)

async def websocket_process_api(resp: web.WebSocketResponse, data: Any):
    res = await process_api(data.get("event", None), data.get("data", None), data.get("echo_id", None))
    if resp.closed:
        return
    await resp.send_json(res, dumps=json_dumps)


async def process_api(
    event: Optional[str],
    req_data: Any,
    echo_id: Optional[str] = None
) -> Any:
    try:
        if event is None:
            return utils.ServiceError(
                "ServiceError",
                400,
                "Bad Request",
                "Event is required"
            )
        resp = await handle_api(event, req_data)
    except:
        logger.traceback()
        resp = utils.ServiceError(
            "ServiceError",
            500,
            "Internal Server Error",
            "ServiceError"
        )
    response = {
        "event": event,
        "data": resp, 
    }
    if echo_id is not None:
        response["echo_id"] = echo_id
    return response

async def handle_api(
    event: str,
    req_data: Any
) -> Any:
    if event == "runtime":
        data = {
            "runtime": utils.get_runtime(),
            "timestamp": time.time()
        }
        if isinstance(req_data, (int, float)):
            data["browser"] = req_data
        return data
    if event == "status":
        return {
            "clusters": len(cluster.clusters.clusters),
            "storages": len(cluster.clusters.storage_manager.storages),
            "online_clusters": len(list(filter(lambda x: x.enabled, cluster.clusters.clusters))),
            "online_storages": len(cluster.clusters.storage_manager.available_storages)
        }
    if event == "qps":
        config = APIQPSConfig()
        if isinstance(req_data, dict) and "count" in req_data and "interval" in req_data:
            config.count = req_data["count"]
            config.interval = req_data["interval"]
        if config.count * config.interval > counter.max:
            config = APIQPSConfig()
        info = counter.last()
        c = int(info._) if info is not None else 0
        start_timestamp = int(time.time() - c)
        c -= c % 5
        start_timestamp -= start_timestamp % 5
        total = config.count * config.interval
        raw_data = {
            int(q._): q.value for q in counter.all_qps if q._ > c - total
        }
        return {
            units.format_time(i + start_timestamp): (sum((raw_data.get(i + j, 0) for j in range(5))))
            for i in range(c - 300, c, 5)
        }
    if event == "systeminfo":
        val = counter.last()
        ret_data = {
            "cpu": 0,
            "memory": 0,
            "connection": {
                "tcp": 0,
                "udp": 0
            },
            "loads": 0
        }
        if val is not None:
            ret_data["cpu"] = val.value.cpu_usage
            ret_data["memory"] = val.value.memory_usage
            ret_data["connection"]["tcp"] = val.value.connection.tcp
            ret_data["connection"]["udp"] = val.value.connection.udp
            c = int(val._) if val is not None else 0
            c -= 300
            loads = [
                i.cpu for i in counter.all_system_info
                if i._ > c
            ]
            ret_data["loads"] = sum(loads) / len(loads) if loads else 0
        return ret_data
    if event == "systeminfo_loads":
        info = counter.last()
        c = int(info._) if info is not None else 0
        start_timestamp = int(time.time() - c)
        c -= c % 5
        start_timestamp -= start_timestamp % 5
        total = req_data if isinstance(req_data, int) else 60
        return {
            units.format_time(q._ + start_timestamp): q for q in counter.all_system_info if q._ > c - total
        }
    if event == "storage_keys":
        session = db.SESSION.get_session()
        q = session.query(db.StorageUniqueIDTable)
        return [
            {
                "id": item.unique_id,
                "data": json.loads(str(item.data) or "{}")
            } for item in q.all()
        ]
    if event == "cluster_statistics_hourly":
        hour = get_query_day_tohour(0)
        session = db.SESSION.get_session()
        q = session.query(db.ClusterStatisticsTable).filter(
            db.ClusterStatisticsTable.hour >= hour
        ).order_by(db.ClusterStatisticsTable.hour, db.ClusterStatisticsTable.cluster)
        hourly_data: defaultdict[str, list[APIStatistics]] = defaultdict(list)
        for item in q.all():
            hourly_data[item.cluster].append( # type: ignore
                APIStatistics(
                    item.hour - hour,# type: ignore
                    int(item.bytes), # type: ignore
                    int(item.hits), # type: ignore
                )
            )
        return hourly_data
    
    if event == "cluster_statistics_daily":
        hour = get_query_day_tohour(30)
        session = db.SESSION.get_session()
        q = session.query(db.ClusterStatisticsTable).filter(
            db.ClusterStatisticsTable.hour >= hour
        ).order_by(db.ClusterStatisticsTable.hour, db.ClusterStatisticsTable.cluster)
        temp_data: defaultdict[str, defaultdict[int, APIStatistics]] = defaultdict(lambda: defaultdict(lambda: APIStatistics("", 0, 0)))
        for item in q.all():
            cluster_id = str(item.cluster)
            hits = int(item.hits)  # type: ignore
            bytes = int(item.bytes) # type: ignore
            day = (int(item.hour) + UTC // 3600) // 24 # type: ignore
            temp_data[cluster_id][day].bytes += bytes
            temp_data[cluster_id][day].hits += hits
        days_data: defaultdict[str, list[APIStatistics]] = defaultdict(list)
        for cluster_id, data in temp_data.items():
            for day, item in data.items():
                days_data[cluster_id].append(APIStatistics(units.format_date(day * 86400), item.bytes, item.hits))
        return days_data

    if event == "storage_statistics_hourly":
        hour = get_query_day_tohour(0)
        session = db.SESSION.get_session()
        q = session.query(db.StorageStatisticsTable).filter(
            db.StorageStatisticsTable.hour >= hour
        ).order_by(db.StorageStatisticsTable.hour)
        hourly_data: defaultdict[str, list[APIStatistics]] = defaultdict(list)
        for item in q.all():
            hourly_data[item.storage].append( # type: ignore
                APIStatistics(
                    int(item.hour - hour), # type: ignore
                    int(item.bytes), # type: ignore
                    int(item.hits), # type: ignore
                )
            )
        return hourly_data
    
    if event == "storage_statistics_daily":
        hour = get_query_day_tohour(30)
        session = db.SESSION.get_session()
        q = session.query(db.StorageStatisticsTable).filter(
            db.StorageStatisticsTable.hour >= hour
        ).order_by(db.StorageStatisticsTable.hour)
        temp_data: defaultdict[str, defaultdict[int, APIStatistics]] = defaultdict(lambda: defaultdict(lambda: APIStatistics("", 0, 0)))
        for item in q.all():
            storage_id = str(item.storage)
            hits = int(item.hits)  # type: ignore
            bytes = int(item.bytes) # type: ignore
            day = (int(item.hour) + UTC // 3600) // 24 # type: ignore
            temp_data[storage_id][day].bytes += bytes
            temp_data[storage_id][day].hits += hits
        days_data: defaultdict[str, list[APIStatistics]] = defaultdict(list)
        for storage_id, data in temp_data.items():
            for day, item in data.items():
                days_data[storage_id].append(APIStatistics(units.format_date(day * 86400), item.bytes, item.hits))
        return days_data
    
    if event == "response_hourly":
        hour = get_query_day_tohour(30)
        session = db.SESSION.get_session()
        q = session.query(db.ResponseTable).filter(
            db.ResponseTable.hour >= hour
        ).order_by(db.ResponseTable.hour)
        
        resp_hourly_data: list[APIResponseStatistics] = []
        for item in q.all():
            resp_hourly_data.append(APIResponseStatistics(
                int(str(item.hour - hour)),
                int(str(item.success)),
                int(str(item.partial)),
                int(str(item.forbidden)),
                int(str(item.not_found)),
                int(str(item.error)),
                int(str(item.redirect)),
            ))
        return resp_hourly_data

    if event == "response_daily":
        day = get_query_day_tohour(30)
        session = db.SESSION.get_session()
        q = session.query(db.ResponseTable).filter(
            db.ResponseTable.hour >= day
        ).order_by(db.ResponseTable.hour)

        temp_resp_data: defaultdict[int, APIResponseStatistics] = defaultdict(lambda: APIResponseStatistics("", 0, 0, 0, 0, 0, 0))
        for item in q.all():
            success = int(str(item.success))
            partial = int(str(item.partial))
            forbidden = int(str(item.forbidden))
            not_found = int(str(item.not_found))
            error = int(str(item.error))
            redirect = int(str(item.redirect))
            day = (int(item.hour) + UTC // 3600) // 24 # type: ignore

            temp_resp_data[day].success += success
            temp_resp_data[day].partial += partial
            temp_resp_data[day].forbidden += forbidden
            temp_resp_data[day].not_found += not_found
            temp_resp_data[day].error += error
            temp_resp_data[day].redirect += redirect

        resp_daily_data: list[APIResponseStatistics] = []
        for day, item in temp_resp_data.items():
            resp_daily_data.append(APIResponseStatistics(
                units.format_date(day * 86400),
                item.success,
                item.partial,
                item.forbidden,
                item.not_found,
                item.error,
                item.redirect,
            ))
        return resp_daily_data
        
    if event == "response_geo":
        day = 1
        if isinstance(req_data, int):
            day = req_data
        day = max(1, min(30, day))
        return await utils.run_sync(query_geo_address, day)

    if event == "response_user_agents":
        day = 1
        if isinstance(req_data, int):
            day = req_data
        day = max(1, min(30, day))
        session = db.SESSION.get_session()
        q = session.query(db.ResponseTable).filter(
            db.ResponseTable.hour >= get_query_day_tohour(day)
        ).order_by(db.ResponseTable.hour)
        ua_data: defaultdict[str, int] = defaultdict(int)
        for item in q.all():
            user_agents = db.decompress(item.user_agents)  # type: ignore
            for ua, count in user_agents.items():
                ua_data[ua] += count
        return ua_data

    if event == "warden":
        if not os.path.exists(f"{logger.dir}/warden-error.log"):
            return []
        with open(f"{logger.dir}/warden-error.log", "r") as f:
            content = f.read()
            return [
                json.loads(line) for line in content.split("\n") if line
            ]

    return None

def get_query_day_tohour(day: int):
    t = int(time.time())
    return int((t - ((t + UTC) % 86400) - 86400 * day) / 3600)

def get_query_hour_tohour(hour: int):
    t = int(time.time())
    return int((t - ((t + UTC) % 3600) - 3600 * hour) / 3600)

def query_geo_address(day: int):
    session = db.SESSION.get_session()
    q = session.query(db.ResponseTable).filter(
        db.ResponseTable.hour >= get_query_day_tohour(day)
    ).order_by(db.ResponseTable.hour)
    merge_ip_tables: defaultdict[str, int] = defaultdict(int)
    geo_data: defaultdict[str, int] = defaultdict(int)
    for item in q.all():
        ip_tables = db.decompress(item.ip_tables) # type: ignore
        for ip, count in ip_tables.items():
            merge_ip_tables[ip] += count
    for ip, count in merge_ip_tables.items():
        address = query_address(ip)
        geo_data[address] += count

    return geo_data

def query_address(address: str) -> str:
    if address in IPDB_CACHE:
        return IPDB_CACHE[address]
    IPDB_CACHE[address] = _query_address(address)
    return IPDB_CACHE[address]

def _query_address(address: str) -> str:
    res = IPDB.find_info(address, "CN")
    if res is None:
        return ""
    if not res.country_name:
        return ""
    if res.country_name == "中国":
        return (res.country_name + " " + res.region_name).strip()
    return res.country_name

def record():
    global running
    while running:
        memory            = process.memory_info()
        connection = process.net_connections()
        stats = SystemInfo(
            cpu_usage=process.cpu_percent(interval=1),
            memory_usage=memory.vms,
            connection=ConnectionStatistics(
                tcp=len([c for c in connection if c.type == socket.SOCK_STREAM]),
                udp=len([c for c in connection if c.type == socket.SOCK_DGRAM])
            ),
            clusters=[
                cluster.id for cluster in cluster.clusters.clusters if cluster.enabled
            ],
            qps=0
        )
        current = utils.get_runtime() - 1
        stats.qps = time_qps[int(current)]
        del time_qps[int(current)]
        counter.add(stats)

async def init():
    global task
    task = threading.Thread(target=record)
    task.start()
    if config.const.auto_sync_assets:
        scheduler.run_repeat_later(
            sync_assets,
            5,
            interval=3600
        )

async def unload():
    global running
    running = 0

async def sync_assets():
    async def get_dir_list(path: str = "/"):
        result = []
        if not path.startswith("/"):
            path = f"/{path}"
        async with session.get(
            f"/repos/{GITHUB_REPO}/contents{path}"
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                for item in data:
                    if item["type"] == "file":
                        result.append(GithubPath(
                            path=item["path"],
                            size=item["size"],
                            sha=item["sha"]
                        ))
                    elif item["type"] == "dir":
                        dir = GithubPath(
                            path=item["path"],
                            size=item["size"],
                        )
                        result.append(dir)
                        for sub in await get_dir_list(dir.path):
                            result.append(sub)
        return result
    
    async def get_file(file: GithubPath):
        async with session.get(
            f"/repos/{GITHUB_REPO}/git/blobs/{file.sha}"
        ) as resp:
            if resp.status == 200:
                json_data = await resp.json()
                if resp.status // 100 == 2:
                    data = io.BytesIO()
                    content: str = json_data['content']
                    if json_data.get("encoding") == "base64":
                        data.write(base64.b64decode(json_data['content']))
                    else:
                        logger.warning(f"Unknown encoding {json_data.get('encoding', 'utf-8')}, {json_data}")
                        data.write(content.encode("utf-8"))
                return data
            return io.BytesIO()

    headers = {
        "User-Agent": config.USER_AGENT
    }
    if config.const.github_token:
        headers["Authorization"] = f"Bearer {config.const.github_token}"
    async with aiohttp.ClientSession(
        GITHUB_BASEURL,
        headers=headers
    ) as session:
        res: list[GithubPath] = await get_dir_list("/assets")
        if not res:
            return
        files: dict[GithubPath, io.BytesIO] = {
            file: result
            for file, result in zip(
                [
                    file for file in res if file.is_file
                ],
                await asyncio.gather(*[get_file(file) for file in res if file.is_file])
            )
        }
        old_dirs: list[str] = []
        for local_root, local_dirs, local_files in os.walk("assets"):
            for file in local_files:
                os.remove(os.path.join(local_root, file))
            for dir in local_dirs:
                old_dirs.append(os.path.join(local_root, dir))
        for dir in old_dirs:
            if os.path.exists(dir):
                os.rmdir(dir)
        
        for file in files:
            path = Path(file.path)
            if file.is_dir:
                path.mkdir(exist_ok=True, parents=True)
                continue
            path.parent.mkdir(exist_ok=True, parents=True)
            with open(path, "wb") as f:
                f.write(files[file].getvalue())
        logger.info(f"Synced {len(files)} files")