import os
import time

import psutil

from core import timer as Timer
from core.utils import get_uptime

process: psutil.Process = psutil.Process(os.getpid())
cpus: dict[float, float] = {}


def _cpu():
    global cpus
    while int(os.environ["ASYNCIO_STARTUP"]):
        for _ in range(max(len(cpus) - 600, 0)):
            cpus.pop(0)
        cpus[get_uptime()] = process.cpu_percent(1)


def get_cpus():
    global cpus
    if not cpus:
        return 0
    return sum(cpus) / len(cpus.copy().values())


def get_loads_detail():
    return {
        t + (float(os.getenv("STARTUP") or 0)): v for t, v in cpus.items()
    }

def get_used_memory() -> int:
    info = process.memory_full_info()
    return info.uss


def get_connections() -> int:
    return len(process.connections())


def init():
    Timer.delay(_cpu)
