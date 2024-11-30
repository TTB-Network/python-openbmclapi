import asyncio
import base64
from collections import deque
from dataclasses import asdict, dataclass, is_dataclass
import io
import json
import os
from pathlib import Path
import socket
import threading
from typing import Any, Optional

import aiohttp
import psutil

from core import cluster, config, logger
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
    clusters: list[ClusterInfo]
    qps: int

@dataclass
class CounterValue:
    _: float
    value: SystemInfo

class Counter:
    def __init__(self, max: int = 600):
        self._data: deque[CounterValue] = deque(maxlen=max)
    
    def add(self, value: SystemInfo):
        self._data.append(CounterValue(
            utils.get_runtime(),
            value
        ))

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

    

counter = Counter()
process = psutil.Process(os.getpid())
task: Optional[threading.Thread] = None
running: int = 1
GITHUB_BASEURL = "https://api.github.com"
GITHUB_REPO = "TTB-Network/python-openbmclapi"
websockets: deque[web.WebSocketResponse] = deque()

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
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    websockets.append(ws)
    async for msg in ws:
        print(msg)
    print("exit")
    websockets.remove(ws)
    return ws

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

def parse_json(data: tuple | set | dict | Any):
    if isinstance(data, (list, tuple, set)):
        return [parse_json(data) for data in data]
    elif is_dataclass(data):
        return parse_json(asdict(data)) # type: ignore
    elif isinstance(data, dict):
        return {parse_json(k): parse_json(v) for k, v in data.items()}
    return data

async def api_process(type: str, data: Any):
    ...

async def trigger(type: str, data: Any = None):
    for ws in websockets:
        await ws.send_json({
            'id': 0,
            'namespace': type,
            'data': await api_process(type, data)
        })

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
            clusters=[],
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
            interval=86400
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
        "User-Agent": cluster.USER_AGENT
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