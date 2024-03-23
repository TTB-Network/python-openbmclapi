import os

import psutil

process: psutil.Process = psutil.Process(os.getpid())

def get_used_memory() -> int:
    info = process.memory_full_info()
    return info.uss
def get_connections() -> int:
    return len(process.connections())