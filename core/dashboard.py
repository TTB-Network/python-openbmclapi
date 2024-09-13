from collections import deque
from dataclasses import dataclass
import os
import socket

import psutil

from . import utils

from . import scheduler
from .web import routes as route
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
class SystemInfo:
    cpu_usage: float
    memory_usage: int
    connection: ConnectionStatistics

@dataclass
class CounterValue:
    _: float
    value: SystemInfo

class Counter:
    def __init__(self, max: int = 300):
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
                 }
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

@route.get("/api/system_info")
async def _(request: web.Request):
    return web.json_response(counter.get_json())

route.static("/assets", "./assets")

def record():
    memory           = process.memory_info()
    connection = process.connections()
    stats = SystemInfo(
        cpu_usage=process.cpu_percent(interval=1),
        memory_usage=memory.vms,
        connection=ConnectionStatistics(
            tcp=len([c for c in connection if c.type == socket.SOCK_STREAM]),
            udp=len([c for c in connection if c.type == socket.SOCK_DGRAM])
        )
    )
    counter.add(stats)

async def init():
    scheduler.run_repeat(record, 1)