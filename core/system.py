import os

import psutil

from core.timer import Timer

process: psutil.Process = psutil.Process(os.getpid())
cpus: list[float] = []


def _cpu():
    global cpus
    while int(os.environ["ASYNCIO_STARTUP"]):
        for _ in range(max(len(cpus) - 600, 0)):
            cpus.pop(0)
        cpus.append(process.cpu_percent(1))

def get_cpus():
    global cpus
    if not cpus:
        return 0
    return sum(cpus) / len(cpus)


def get_used_memory() -> int:
    info = process.memory_full_info()
    return info.uss


def get_connections() -> int:
    return len(process.connections())


def init():
    Timer.delay(_cpu)
