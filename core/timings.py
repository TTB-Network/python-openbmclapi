import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from core import utils

import inspect

@dataclass
class Performance:
    name: str
    start: float
    end: float
    stack: list[inspect.FrameInfo]
timings: list[Performance] = []

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
