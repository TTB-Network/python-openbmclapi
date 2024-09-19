from collections import deque
from dataclasses import dataclass
import json
import os
import socket
from typing import Any, Optional

import aiohttp
import psutil

from core import cache, config

from . import utils

from . import scheduler
from .web import (
    routes as route,
    qps as web_qps
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
    
class ClientRoom:
    def __init__(self) -> None:
        self.clients = cache.MemoryStorage()
        self.__default_data = {
            "lastKeepalive": 0,
            "messages": []
        }

    @property
    def _default_data(self):
        return self.__default_data.copy()

    def join_ws(self, id: str):
        self.clients.set(id, self._default_data)
    def join_http(self, id: str):
        self.clients.set(id, self._default_data, 600)

    def keepalive(self, id: str):
        client = self.clients.get(id, self._default_data)
        client["lastKeepalive"] = utils.get_runtime()
        self.clients.set(id, client)

    
    def exit(self, id: str):
        self.clients.delete(f"ws-{id}")
        self.clients.delete(f"http-{id}")

    def send(self, event: str, data: Any, id: Optional[str] = None):
        ids = [_id for _id in self.clients.get_keys() if id is None or (id is not None and _id == id)]
        for id in ids:
            client = self.clients.get(id, self._default_data)
            client["messages"].append({
                "event": event,
                "data": data
            })
            self.clients.set(id, client)

    def get_messages(self, id: str):
        client = self.clients.get(id, self._default_data)
        data: list[Any] = client["messages"].copy()
        client["messages"].clear()
        self.clients.set(id, client)
        return data
    
    

room = ClientRoom()
counter = Counter()
process = psutil.Process(os.getpid())

@route.get('/dashboard/')
@route.get("/dashboard/{tail:.*}")
async def _(request: web.Request):
    return web.FileResponse("./assets/index.html")

@route.get('/')
async def _(request: web.Request):
    return web.HTTPFound('/dashboard/')

@route.get("/favicon.ico")
async def _(request: web.Request):
    return web.FileResponse("./assets/favicon.ico")

@route.get("/api/system_info")
async def _(request: web.Request):
    return web.json_response(counter.get_json())

@route.get("/api/openbmclapi/rank")
async def _(request: web.Request):
    async with aiohttp.ClientSession(
        "bd.bangbang93.com"
    ) as session:
        async with session.get("/openbmclapi/metric/rank") as resp:
            return web.json_response(
                await resp.json(),
            )
        
@route.get("/api")
async def _(request: web.Request):
    if request.headers.get("Connection", "").lower() == "upgrade" and request.headers.get("Upgrade", "").lower() == "websocket":
        try:
            ws = web.WebSocketResponse()
            ws.can_prepare(request)
            await ws.prepare(request)
            id: str = request.query.get("id") # type: ignore
            room.join_ws(id)
            while not ws.closed:
                try:
                    raw_data = json.loads((await ws.receive()).data)
                    messages = room.get_messages(id)
                    messages.append({
                        "echo_id": raw_data.get("echo_id"),
                        "event": raw_data["event"],
                        "data": raw_data
                    })
                    if raw_data["event"] == "keepalive":
                        room.keepalive(id)
                    await ws.send_json(messages)
                except:
                    break
            room.exit(id)
            return ws
        except:
            ...
    return web.HTTPNotFound()

@route.post("/api")
async def _(request: web.Request):
    try:
        id: str = request.query.get("id") # type: ignore
        room.join_http(id)
        body = await request.read()
        raw_data = json.loads(body)
        messages = room.get_messages(id)
        messages.append({
            "event": raw_data["event"],
            "echo_id": raw_data.get("echo_id"),
            "data": raw_data
        })
        if raw_data["event"] == "disconnect":
            room.exit(id)
        if raw_data["event"] == "keepalive":
            room.keepalive(id)
        return web.json_response(messages)
    except:
        return web.HTTPInternalServerError()
    

route.static("/assets", "./assets")

def record():
    global web_qps
    memory            = process.memory_info()
    connection = process.connections()
    stats = SystemInfo(
        cpu_usage=process.cpu_percent(interval=1),
        memory_usage=memory.vms,
        connection=ConnectionStatistics(
            tcp=len([c for c in connection if c.type == socket.SOCK_STREAM]),
            udp=len([c for c in connection if c.type == socket.SOCK_DGRAM])
        ),
        clusters=[],
        qps=web_qps
    )
    web_qps -= stats.qps
    counter.add(stats)

async def init():
    scheduler.run_repeat(record, 1)