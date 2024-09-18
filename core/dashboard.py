from collections import deque
from dataclasses import dataclass
import json
import os
import socket

import aiohttp
import psutil

from core import config

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
        ws = web.WebSocketResponse()
        ws.can_prepare(request)
        await ws.prepare(request)
        await ws.send_json({
            "event": "echo",
            "data": "hello world",
            "echo_id": None
        })
        while not ws.closed:
            try:
                raw_data = await ws.receive()
                try:
                    print(raw_data)
                except:
                    ...
            except:
                break
        return ws
    else:
        return web.json_response({
        })
    

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