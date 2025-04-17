from collections import defaultdict, deque
import hashlib
import io
import math
from pathlib import Path
import time
from typing import (
    Any, 
    Awaitable, 
    Callable, 
    Optional, 
    TypeVar, 
)

import aiohttp
import anyio
import anyio.abc
import cachetools
from tqdm import tqdm
from functools import lru_cache
import apscheduler.schedulers.asyncio
from tianxiu2b2t.anyio.future import Future

from .logger import logger

from .abc import CertificateType
from .config import cfg

K = TypeVar("K")
V = TypeVar("V") 
T = TypeVar("T")

class AvroParser:
    def __init__(
        self,
        data: bytes
    ):
        self.data = io.BytesIO(data)

    def read_long(self): 
        result, shift = 0, 0
        while True:
            byte = ord(self.data.read(1))
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
        return (result >> 1) ^ -(result & 1)
    
    def read_string(self):
        return self.data.read(self.read_long()).decode('utf-8')

class Event:
    def __init__(
        self
    ):
        self._fut: defaultdict[str, deque[Future]] = defaultdict(deque)
        self._task_group = None
        self._callbacks: defaultdict[str, deque[Callable]] = defaultdict(deque)

    def emit(
        self,
        name: str,
        data: Any = None
    ):
        for fut in self._fut[name]:
            fut.set_result(data)
        assert self._task_group 
        for cb in self._callbacks[name]:
            self._task_group.start_soon(cb, data)
        
    async def setup(
        self,
        task_group: anyio.abc.TaskGroup
    ):
        self._task_group = task_group
        
    def callback(
        self,
        name: str
    ):
        def _callback(coro: Callable):
            async def cb(data):
                await coro(data)
            self._callbacks[name].append(cb)
            return coro
        return _callback

# 分割工作总量
def split_workload(
    items: list[Any],
    n: int
):
    return [items[i::n] for i in range(n)]

def schedule_once(
    task_group: anyio.abc.TaskGroup,
    func: Callable[..., Awaitable],
    delay: float,
    *args, **kwargs
):
    async def _schedule_once():
        await anyio.sleep(delay)
        await func(*args, **kwargs)
    task_group.start_soon(_schedule_once)


def get_hash_obj(
    hash: str
):
    if len(hash) == 32:
        return hashlib.md5()
    return hashlib.sha1()

@lru_cache(maxsize=1024)
def get_certificate_type() -> CertificateType:
    ret = CertificateType.CLUSTER
    if cfg.get("web.proxy"):
        ret = CertificateType.PROXY
    else:
        key, cert = cfg.get("cert.key"), cfg.get("cert.cert")
        if key and cert:
            key_file, cert_file = Path(key), Path(cert)
            if key_file.exists() and cert_file.exists() and cert_file.stat().st_size > 0 and key_file.stat().st_size > 0:
                ret = CertificateType.BYOC
    logger.tinfo(f"web.byoc", type=ret)
    return ret

def get_range_size(range: str, size: Optional[int] = None):
    if range.startswith("bytes="):
        range = range[6:]
    if "-" in range:
        start, end = range.split("-")
        if end:
            return int(end) - int(start) + 1
        elif size is not None:
            return size - int(start)
    elif size is not None:
        start = int(range)
        return size - start
    return size

def parse_range(range: str):
    if not range or not range.startswith("bytes="):
        return None
    range = range[6:]
    start, end = range.split("-")
    return RangeResult(
        start=int(start),
        end=int(end) if end else None
    )

class SubTQDM:
    def __init__(self, total: float, description: str = "", position: int = 0, leave: bool = True, **kwargs):
        self.total = total
        self.description = description
        self.position = position
        self.leave = leave
        self.kwargs = kwargs

        # 创建独立的 tqdm 进度条
        self._tqdm = tqdm(
            total=total,
            desc=description,
            position=position,
            leave=leave,
            dynamic_ncols=True,
            **kwargs
        )

    def update(self, n: float = 1):
        self._tqdm.update(n)

    def close(self):
        self._tqdm.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class MultiTQDM:
    def __init__(self, total: float = 0, description: str = "", position: int = 0, **kwargs):
        self.total = total
        self.description = description
        self.position = position
        self.kwargs = kwargs

        # 主进度条
        self._total_tqdm = tqdm(
            total=total,
            desc=description,
            position=position,
            dynamic_ncols=True,
            **kwargs
        )

        # 子进度条列表
        self._current_bars = []
        self._next_position = position + 1  # 下一个可用的位置

    @property
    def total_tqdm(self):
        return self._total_tqdm

    def sub(self, total: float = 0, description: str = "", **kwargs) -> SubTQDM:
        """创建一个新的子进度条"""
        sub_tqdm = SubTQDM(
            total=total,
            description=description,
            position=self._next_position,
            **kwargs
        )
        self._current_bars.append(sub_tqdm)
        self._next_position += 1
        return sub_tqdm

    def update(self, n: float = 1):
        self._total_tqdm.update(n)

    def set_postfix_str(self, postfix: str):
        self._total_tqdm.set_postfix_str(postfix)

    def close(self):
        """关闭所有进度条"""
        for sub_tqdm in self._current_bars:
            sub_tqdm.close()
        self._total_tqdm.close()

    def __del__(self):
        """在 MultiTQDM 被销毁时，关闭所有子进度条"""
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class RangeResult:
    def __init__(
        self,
        start: int,
        end: Optional[int],
    ):
        self.start = start
        self.end = end

class UnboundTTLCache(cachetools.TTLCache[K, V]):
    def __init__(self, maxsize: Optional[float], ttl: float, timer=time.monotonic):
        cachetools.TTLCache.__init__(self, maxsize or math.inf, ttl, timer)

    @property
    def maxsize(self):
        return None

def debug_aiohttp_response(
    response: aiohttp.ClientResponse,
    body: Any
):
    logger.debug(
        "aiohttp response",
        response.status,
        response.reason,
        response.headers,
        body
    )

event = Event()

scheduler = apscheduler.schedulers.asyncio.AsyncIOScheduler(
    timezone="Asia/Shanghai",
    missfire_grace_time=99999999,
    coalesce=True,
)