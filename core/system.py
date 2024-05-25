import os
import time

import psutil
import platform
from core import logger, scheduler
from core.utils import get_uptime, format_time
from core.env import env
import subprocess

def get_connection():
    if platform.system() == "Linux":
        result = subprocess.run(['conntrack', '-C'], capture_output=True, text=True, check=True)
        output = result.stdout
        connection = int(output.split()[-1]) 
        return connection
    if platform.system() == "Windows":
        result = subprocess.run(['netstat', '-n'], capture_output=True, text=True, check=True)
        output = result.stdout
        connection = len([line for line in output.splitlines() if "ESTABLISHED" in line])
        return connection
process: psutil.Process = psutil.Process(os.getpid())
cpus: dict[float, float] = {}
memories: dict[float, int] = {}
connections: dict[float, get_connection] = {}
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
    connections[cur] = get_connection()
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
    startup: float = env["STARTUP"] + -time.timezone
    return {
        "cpu": {format_time(t + startup): v for t, v in get_filled(cpus.copy()).items()},
        "memory": {format_time(t + startup): v for t, v in get_filled(memories.copy()).items()},
        "connections": {format_time(t + startup): v for t, v in get_filled_list(connections.copy()).items()},
    }


def get_filled(data: dict[float, float]):
    key = min(list(data.keys()) or [0])
    for _ in range(60 - len(data)):
        key -= 1
        data[key] = 0
    data = dict(sorted(data.items()))
    for _ in list(data.keys())[60:]:
        data.pop(_)
    return data

def get_filled_list(data: dict[float, list]):
    key = min(list(data.keys()) or [0])
    for _ in range(60 - len(data)):
        key -= 1
        data[key] = []
    data = dict(sorted(data.items()))
    for _ in list(data.keys())[60:]:
        data.pop(_)
    return data

def get_used_memory() -> int:
    info = process.memory_full_info()
    return info.uss


def get_connections() -> int:
    return get_connection()


def init():
    logger.tinfo("system.info.loading")
    scheduler.repeat(_run)
