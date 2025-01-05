import asyncio
import base64
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, fields, is_dataclass
import datetime
import enum
import io
import json
import os
from pathlib import Path
import socket
import threading
import time
from typing import Any, Callable, Optional

import aiohttp
import psutil

from . import cache, cluster, config, logger, units, utils, scheduler, ipsearcher, database as db

from .web import (
    routes as route,
    time_qps
)
from aiohttp import web

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
    success: int = 0
    partial: int = 0
    forbidden: int = 0
    not_found: int = 0
    error: int = 0
    redirect: int = 0

@dataclass
class SSEClient:
    request: web.Request
    resp: web.StreamResponse
    fut: asyncio.Future

@dataclass
class SSEMessage:
    event: str
    data: Any
    id: utils.ObjectId

class SSEEmiter:
    def __init__(
        self,
        timeout: Optional[int] = None,
        /,
        loop = asyncio.get_event_loop()
    ):
        self._timeout = timeout or 0
        self._connections: deque[SSEClient] = deque()
        self._cache: cache.TimeoutCache[utils.ObjectId, SSEMessage] = cache.TimeoutCache(
            300
        )
        self._loop = loop

    async def send(
        self,
        message: SSEMessage
    ):
        for client in self._connections.copy():
            await self.send_client(
                client,
                message
            )

    async def raw_send_client(
        self,
        client: SSEClient,
        id: Optional[str] = None,
        event: Optional[str] = None,
        data: Optional[str] = None
    ):
        buffer = io.StringIO()
        for item in {
            "id": id,
            "event": event,
            "data": data
        }.items():
            if item[1] is not None:
                buffer.write(f"{item[0]}: {item[1]}\n")
        buffer.write("\n")
        await client.resp.write(buffer.getvalue().encode("utf-8"))
    
    async def send_client(
        self,
        client: SSEClient,
        message: SSEMessage
    ):
        if client.fut.done():
            await self.close_client(client)
            return
        if client.request.transport is None or client.request.transport.is_closing():
            await self.close_client(client)
            return
        try:
            await self.raw_send_client(
                client,
                id=str(message.id),
                event="message",
                data=json_dumps(
                    {
                        "event": message.event,
                        "data": message.data
                    }
                )
            )
        except:
            await self.close_client(client)


    async def request(
        self,
        request: web.Request,
    ):
        resp = web.StreamResponse(
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            }
        )
        try:
            client = SSEClient(
                request=request,
                resp=resp,
                fut=asyncio.get_event_loop().create_future()
            )
            await resp.prepare(request)
            self._connections.append(client)
            last_event_id: str = request.headers.get("Last-Event-ID", "0" * 24)
            last_id = utils.ObjectId(last_event_id)
            for message in self._cache.keys():
                if message.generation_time <= last_id.generation_time:
                    break
                await self.send_client(
                    client,
                    self._cache.get(message)
                )
                    
            try:
                tasks = [
                    client.fut
                ]
                for t in (
                    request.task,
                    resp.task
                ):
                    if t is not None:
                        tasks.append(t)
                await asyncio.gather(*tasks)
            except:
                await self.close_client(client)
            # wait request closed or timeout
        except:
            ...
        return resp

    async def push_message(
        self,
        event: str,
        data: Any
    ):
        message = SSEMessage(
            event=event,
            data=data,
            id=utils.ObjectId()
        )
        self._cache.set(message.id, message)
        if not self._connections:
            return
        await self.send(message)

    async def close_client(
        self,
        client: SSEClient
    ):
        try:
            client.fut.cancel(None)
        except:
            logger.traceback()
            self._connections.remove(client)

    async def close(
        self
    ):
        for client in self._connections.copy():
            await self.close_client(client)

class APIManager:
    def __init__(
        self
    ):
        self.events: dict[str, Callable[[Any], Any]] = {}
    
    def on(
        self,
        event: str
    ):
        def decorator(func: Callable[[Any], Any]):
            self.events[event] = func
            return func
        return decorator

    async def emit(
        self,
        event: str,
        data: Any
    ):
        if event in self.events:
            handler = self.events[event]
            if asyncio.iscoroutinefunction(handler):
                return await asyncio.create_task(
                    handler(data)
                )
            else:
                return await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: handler(data),
                )

counter = Counter()
process = psutil.Process(os.getpid())
task: Optional[threading.Thread] = None
running: int = 1
status_task = None
GITHUB_BASEURL = "https://api.github.com"
GITHUB_REPO = "TTB-Network/python-openbmclapi"
UTC = 28800 # UTC + 8 hours (seconds)
IPDB_CACHE: dict[str, str] = {}
SSEEMIT = SSEEmiter()
LAST_TQDM = False
API = APIManager()
IPSEARCHER = ipsearcher.City(
    "./assets/ipdb.ipdb"
)
IPSEARCHER_CACHE: dict[str, ipsearcher.CityInfo] = {}
IPWARNING: set[str] = set()

@route.get("/service-worker.js")
async def _(request: web.Request):
    return web.FileResponse("./assets/js/service-worker.js")

@route.get('/')
@route.get('/pages')
@route.get("/pages/{tail:.*}")
async def _(request: web.Request):
    return web.FileResponse("./assets/index.html")

@route.get("/favicon.ico")
async def _(request: web.Request):
    return web.FileResponse("./assets/favicon.ico")

@route.get("/assets/ip2region.xdb") # 禁止访问 ip2region.xdb
async def _(request: web.Request):
    return web.Response(status=404)

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

@route.get("/api_event") # sse
async def _(request: web.Request):
    return await SSEEMIT.request(request)

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

route.static("/assets", "./assets")

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.strftime("%Y-%m-%d %H:%M:%S")
        if is_dataclass(o):
            return asdict(o) # type: ignore
        if isinstance(o, enum.Enum):
            return o.value
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
        resp = await API.emit(event, req_data)
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

# handle api

@API.on("runtime")
def _(req_data: Any) -> Any:
    data = {
        "runtime": utils.get_runtime(),
        "timestamp": time.time()
    }
    if isinstance(req_data, (int, float)):
        data["browser"] = req_data
    return data

@API.on("status")
def _(req_data: Any) -> Any:
    return {
        "clusters": len(cluster.clusters.clusters),
        "storages": len(cluster.clusters.storage_manager.storages),
        "online_clusters": len(list(filter(lambda x: x.enabled, cluster.clusters.clusters))),
        "online_storages": len(cluster.clusters.storage_manager.available_storages)
    }

@API.on("qps")
def _(req_data: Any) -> Any:
    qps_config = APIQPSConfig()
    if isinstance(req_data, dict) and "count" in req_data and "interval" in req_data:
        qps_config.count = req_data["count"]
        qps_config.interval = req_data["interval"]
    if qps_config.count * qps_config.interval > counter.max:
        qps_config = APIQPSConfig()
    info = counter.last()
    c = int(info._) if info is not None else 0
    start_timestamp = int(time.time() - c)
    c -= c % 5
    start_timestamp -= start_timestamp % 5
    total = qps_config.count * qps_config.interval
    raw_data = {
        int(q._): q.value for q in counter.all_qps if q._ > c - total
    }
    return {
        units.format_time(i + start_timestamp): (sum((raw_data.get(i + j, 0) for j in range(5))))
        for i in range(c - 300, c, 5)
    }

@API.on("systeminfo")
def _(req_data: Any) -> Any:
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

@API.on("systeminfo_loads")
def _(req_data: Any) -> Any:
    info = counter.last()
    c = int(info._) if info is not None else 0
    start_timestamp = int(time.time() - c)
    c -= c % 5
    start_timestamp -= start_timestamp % 5
    total = req_data if isinstance(req_data, int) else 60
    return {
        units.format_time(q._ + start_timestamp): q for q in counter.all_system_info if q._ > c - total
    }

@API.on("storage_keys")
def _(req_data: Any) -> Any:
    with db.SESSION as session:
        q = session.query(db.StorageUniqueIDTable)
    return [
        {
            "id": item.unique_id,
            "data": json.loads(str(item.data) or "{}")
        } for item in q.all()
    ]

@API.on("cluster_statistics_hourly")
def _(req_data: Any) -> Any:
    hour = get_query_day_tohour(0)
    with db.SESSION as session:
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

@API.on("storage_statistics_daily")
def _(req_data: Any) -> Any:
    hour = get_query_day_tohour(30)
    with db.SESSION as session:
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

@API.on("storage_statistics_hourly")
def _(req_data: Any) -> Any:
    hour = get_query_day_tohour(0)
    with db.SESSION as session:
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

@API.on("storage_statistics_daily")
def _(req_data: Any) -> Any:
    hour = get_query_day_tohour(30)
    with db.SESSION as session:
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

@API.on("clusters_event")
def _(req_data: Any) -> Any:
    return cluster.clusters.event_logger.read()

@API.on("clusters_name")
async def _(req_data: Any) -> Any:
    clusters: dict[str, str] = {}
    async with aiohttp.ClientSession() as session:
        async with session.get(config.const.rank_clusters_url) as resp:
            resp = await resp.json()
            for item in resp:
                clusters[item["_id"]] = item["name"]

    return {
        c.id: clusters.get(c.id, c.id) for c in cluster.clusters.clusters
    }

@API.on("rank")
async def _(req_data: Any) -> Any:
    async with aiohttp.ClientSession() as session:
        async with session.get(config.const.rank_clusters_url) as resp:
            return await resp.json()

@API.on("response_ip_access")
def _(req_data: Any) -> Any:
    day = 1
    if isinstance(req_data, int) and req_data == 1 or req_data == 7 or req_data == 30:
        day = req_data
    query_data = query_addresses(day * 24)
    temp_data: defaultdict[str, set] = defaultdict(set)
    if day > 7:
        for hour, data in query_data.items():
            date = datetime.datetime.fromtimestamp(hour * 3600)
            key = f"{date.year:04d}-{date.month:02d}-{date.day:02d}"
            temp_data[key] |= data.keys()
    else:
        for hour, data in query_data.items():
            date = datetime.datetime.fromtimestamp(hour * 3600)
            hour = date.hour
            key = f"{date.year:04d}-{date.month:02d}-{date.day:02d} {date.hour:02d}:{date.minute:02d}"
            temp_data[key] |= data.keys()
    resp_data: defaultdict[str, int] = defaultdict(int)
    for key, data in temp_data.items():
        resp_data[key] = len(data)
    return resp_data

@API.on("response_user_agents")
def _(req_data: Any) -> Any:
    day = 1
    if isinstance(req_data, int) and req_data == 1 or req_data == 7 or req_data == 30:
        day = req_data
    hour = get_query_hour_tohour(day * 24)
    data: defaultdict[str, int] = defaultdict(int)
    with db.SESSION as session:
        q = session.query(db.ResponseTable).filter(
            db.ResponseTable.hour >= hour
        ).order_by(db.ResponseTable.hour)
        for item in q.all():
            ip_tables = db.decompress(item.user_agents)  # type: ignore
            for user_agent, count in ip_tables.items():
                data[user_agent] += count
    return data

@API.on("response_status")
def _(req_data: Any) -> Any:
    day = 1
    if isinstance(req_data, int) and req_data == 1 or req_data == 7 or req_data == 30:
        day = req_data
    hour = get_query_hour_tohour(day * 24)
    data: APIResponseStatistics = APIResponseStatistics()
    data_fields = fields(APIResponseStatistics)
    with db.SESSION as session:
        q = session.query(db.ResponseTable).filter(
            db.ResponseTable.hour >= hour
        ).order_by(db.ResponseTable.hour)
        for item in q.all():
            for field in data_fields:
                setattr(data, field.name, getattr(data, field.name) + getattr(item, field.name))
    return data
            
@API.on("response_geo")
def _(req_data: Any) -> Any:
    #raise NotImplementedError("Not implemented yet")
    options = {
        "cn": False,
        "day": 1
    }
    if isinstance(req_data, dict):
        options.update(req_data)
    day = options["day"]
    if isinstance(day, int) and day == 1 or day == 7 or day == 30:
        day = day
    else:
        day = 1
    return query_geo(
        day,
        bool(options["cn"])
    )

@API.on("cluster_statistics_daily")
def _(req_data: Any) -> Any:
    hour = get_query_day_tohour(30)
    with db.SESSION as session:
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

@API.on("storage_statistics_daily")
def _(req_data: Any) -> Any:
    hour = get_query_day_tohour(30)
    with db.SESSION as session:
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

@API.on("clusters_bandwidth")
def _(req_data: Any) -> Any:
    return cluster.BANDWIDTH_COUNTER.get(max(1, req_data) if isinstance(req_data, int) else 1)

@DeprecationWarning
async def handle_api(
    event: str,
    req_data: Any
) -> Any:
    """if event == "response_hourly":
        hour = get_query_day_tohour(0)
        with db.SESSION as session:
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
        with db.SESSION as session:
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
        with db.SESSION as session:
            q = session.query(db.ResponseTable).filter(
                db.ResponseTable.hour >= get_query_day_tohour(day)
            ).order_by(db.ResponseTable.hour)
            ua_data: defaultdict[str, int] = defaultdict(int)
            for item in q.all():
                user_agents = db.decompress(item.user_agents)  # type: ignore
                for ua, count in user_agents.items():
                    ua_data[ua] += count
        return ua_data
    """


    return None

async def push_tqdm():
    global LAST_TQDM
    data = []
    for pbar in utils.wrapper_tqdms:
        data.append({
            "desc": pbar.pbar.desc,
            "total": pbar.pbar.total,
            "current": pbar.pbar.n,
            "unit": pbar.pbar.unit,
            "speed": list(pbar.speed),
            "postfix": pbar.pbar.postfix,
            "start_time": pbar.start_time,
            "current_time": time.time()
        })
    if LAST_TQDM != bool(data) and not data:
        await SSEEMIT.push_message(
            "progress", data
        )
    LAST_TQDM = bool(data)
    if not data:
        return
    await SSEEMIT.push_message(
        "progress", data
    )

async def push_status():
    global running
    while running:
        try:
            await asyncio.wait_for(utils.status_manager.wait(), timeout=10)
        except:
            ...
        await SSEEMIT.push_message(
            "status", [
                {
                    "name": item.key,
                    "count": item.count,
                    "params": item.params,
                    "start_time": None if item.timestamp == -1 else time.time() - item.timestamp - utils.get_start_runtime(),
                }
                for item in utils.status_manager.status
            ]
        )

def get_query_day_tohour(day: int):
    t = int(time.time())
    return int((t - ((t + UTC) % 86400) - 86400 * day) / 3600)

def get_query_hour_tohour(hour: int):
    t = int(time.time())
    return int((t - ((t + UTC) % 3600) - 3600 * hour) / 3600)

def query_addresses(
    since_hour: int = 24
):
    hour = get_query_hour_tohour(since_hour)
    with db.SESSION as session:
        q = session.query(db.ResponseTable).filter(
            db.ResponseTable.hour >= hour
        ).order_by(db.ResponseTable.hour)
        data: defaultdict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for item in q.all():
            ip_tables = db.decompress(item.ip_tables)  # type: ignore
            for ip, count in ip_tables.items():
                data[item.hour][ip] += count # type: ignore
    return data



def query_geo(
    day: int,
    cn: bool = False
):
    resp_data: defaultdict[str, int] = defaultdict(int)
    threads: list[threading.Thread] = []
    for hour, data in query_addresses(day * 24).items():
        threads.append(threading.Thread(
            target=thread_query_geo,
            args=(data, resp_data, cn)
        ))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    threads.clear()
    return resp_data

def thread_query_geo(
    data: dict[str, int],
    resp_data: defaultdict[str, int],
    cn: bool
):
    for ip, count in data.items():
        address = query_ip(ip)
        if cn and address.country == "CN":
            resp_data[address.province] += count
        else:
            resp_data[address.country] += count

def query_ip(
    ip: str
):
    #cache_res = IPSEARCHER_CACHE.get(ip)
    #if cache_res is not cache.EMPTY:
    #    return cache_res
    if ip in IPSEARCHER_CACHE:
        return IPSEARCHER_CACHE[ip]
    try:
        result = IPSEARCHER.find_info(ip, "CN") or ipsearcher.CityInfo(**{
            "country": "LOCAL",
            "province": "LOCAL"
        })
    except:
        result = ipsearcher.CityInfo(**{
            "country": "None",
            "province": "None"
        })
    IPSEARCHER_CACHE[ip] = result
    return result

"""
def query_geo_address(day: int):
    with db.SESSION as session:
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
"""
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
    global task, status_task
    task = threading.Thread(target=record)
    task.start()
    status_task = asyncio.create_task(push_status())
    scheduler.run_repeat_later(
        push_tqdm,
        0, 
        0.5
    )
    scheduler.run_repeat_later(
        fetch_github_repo,
        5,
        interval=3600
    )

async def unload():
    global running, status_task
    running = 0
    if status_task is not None:
        status_task.cancel()
    await SSEEMIT.close()

async def fetch_github_repo():
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

    async def sync_assets():
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
        if any(
            [
                len(file.getvalue()) == 0 for file in files.values()
            ]
        ):
            logger.error("Failed to sync assets")
            return
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
    
    async def check_update():
        async with session.get(
            f"/repos/{GITHUB_REPO}/releases/latest"
        ) as resp:
            if resp.status == 200:
                json_data = await resp.json()
                tag_name = json_data["tag_name"][1:]
                if tag_name != config.VERSION:
                    logger.tinfo("dashboard.info.new_version", current=config.VERSION, latest=tag_name)
                    return

    headers = {
        "User-Agent": config.USER_AGENT
    }
    if config.const.github_token:
        headers["Authorization"] = f"Bearer {config.const.github_token}"
    async with aiohttp.ClientSession(
        GITHUB_BASEURL,
        headers=headers
    ) as session:
        tasks = [
            check_update()
        ]
        if config.const.auto_sync_assets:
            tasks.append(sync_assets())
        await asyncio.gather(*tasks)