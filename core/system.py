import os

import psutil

from core import logger, scheduler
from core.utils import get_uptime

process: psutil.Process = psutil.Process(os.getpid())
cpus: dict[float, float] = {}
memories: dict[float, int] = {}
connections: dict[float, list["psutil.pconn"]] = {}
length: int = 0
last_curs: list[float] = []


def _run():
    global cpus, memories, connections, length, last_curs
    for _ in range(max(length - 60, 0)):
        cur = last_curs.pop(0)
        if cur in cpus:
            cpus.pop(cur)
        if cur in memories:
            memories.pop(cur)
        if cur in connections:
            connections.pop(cur)
        length -= 1
    cur = get_uptime()
    cpus[cur] = process.cpu_percent(1)
    memories[cur] = process.memory_full_info().uss
    connections[cur] = process.connections()
    length += 1
    last_curs.append(cur)


def get_cpus():
    global cpus
    if not cpus:
        return 0
    arr = cpus.copy().values()
    return sum(arr) / len(arr)


def get_loads_detail():
    global cpus, memories, connections
    offset: float = float(os.getenv("STARTUP") or 0)
    return {
        "cpu": {t + offset: v for t, v in cpus.items()},
        "memory": {t + offset: v for t, v in memories.items()},
        "connections": {t + offset: len(v) for t, v in connections.items()},
    }


def get_used_memory() -> int:
    info = process.memory_full_info()
    return info.uss


def get_connections() -> int:
    return len(process.connections())


def init():
    logger.tinfo("system.info.loading")
    scheduler.repeat(_run)
