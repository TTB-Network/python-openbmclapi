import asyncio
from dataclasses import dataclass
from enum import Enum
import time
from typing import Awaitable, Callable, Optional

from tqdm import tqdm

from core import logger, unit, utils

import inspect

@dataclass
class Performance:
    name: str
    start: float
    end: float
    stack: list[inspect.FrameInfo]
timings: list[Performance] = []

class logTqdmType(Enum):
    BYTES = "bytes"
    IT = "it"

class logTqdm:
    def __init__(self, tqdm: tqdm, type: logTqdmType = logTqdmType.IT) -> None:
        self.tqdm = tqdm
        self.type = type
    def __enter__(self):
        self.start = time.time()

    def __exit__(self, exc_type, exc_value, traceback):
        logger.info(f"{self.tqdm.desc} 已完成，耗时 [{utils.format_stime(time.time() - self.start)}]，数量 [{get_formatter(self.type)(self.tqdm.n)}] 总数 [{get_formatter(self.type)(self.tqdm.total)}]")

def get_formatter(type: logTqdmType):
    if type == logTqdmType.BYTES:
        return unit.format_bytes
    return unit.format_number

def is_coroutine(func):  
    return asyncio.iscoroutinefunction(func)  

def timing(func: Callable[..., Awaitable], name: Optional[str] = None):
    def wrapper(*args, **kwargs):
        start = utils.get_uptime()
        func(*args, **kwargs)
        end = utils.get_uptime()
        _name = name or func.__name__
        stack = inspect.stack()[:-2]
        #timings.append(Performance(_name, start, end, stack))

    async def async_wrapper(*args, **kwargs):
        start = utils.get_uptime()
        await func(*args, **kwargs)
        end = utils.get_uptime()
        _name = name or func.__name__
        stack = inspect.stack()[:-2]
        #timings.append(Performance(_name, start, end, stack))
    
    return async_wrapper if is_coroutine(func) else wrapper
