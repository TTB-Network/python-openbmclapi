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
    Coroutine, 
    TypeVar, 
)

import anyio
import anyio.abc
import cachetools
from tqdm import tqdm
from functools import lru_cache

from .logger import logger

from .abc import CertificateType
from .config import cfg

K = TypeVar("K")
V = TypeVar("V") 
T = TypeVar("T")

class Runtime:
    def __init__(
        self
    ):
        self._monotic = time.monotonic_ns()
        self._perf_counter = time.perf_counter_ns()

    def get_monotic_ns(self):
        return time.monotonic_ns() - self._monotic
    
    def get_perf_counter_ns(self):
        return time.perf_counter_ns() - self._perf_counter
    
    def get_monotic(self):
        return time.monotonic() - self._monotic / 1e9

    def get_perf_counter(self):
        return time.perf_counter() - self._perf_counter / 1e9
    
class TLSHandshake:
    def __init__(
        self,
        version: int,
        sni: Optional[str]   
    ):
        self.version = version
        self.sni = sni

    def __repr__(self) -> str:
        return f"TLSHandshake(version={self.version}, sni={self.sni})"

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

class AnyioFuture:
    def __init__(
        self,
    ):
        self._result = None
        self._setted = False
        self._event = anyio.Event()
    
    def set_result(
        self,
        result: Any
    ):
        if self._setted:
            raise RuntimeError("Future already set")
        self._result = result
        self._setted = True
        self._event.set()

    def result(self):
        if not self._setted:
            raise RuntimeError("Future not set")
        return self._result
    
    async def wait(self):
        await self._event.wait()

    async def __await__(self):
        await self.wait()
        return self.result()

class CustomLock:
    def __init__(
        self,
        locked: bool = False
    ):
        self._locked = locked
        self._fut: deque[AnyioFuture] = deque()

    def acquire(
        self,
    ):
        self._locked = True

    def release(
        self,
    ):
        self._locked = False

        for fut in self._fut:
            fut.set_result(None)

    async def wait(
        self
    ):
        if not self._locked:
            return
        fut = AnyioFuture()
        self._fut.append(fut)
        try:
            await fut.wait()
        finally:
            self._fut.remove(fut)

class Queue[T]:
    def __init__(
        self,
    ):
        self._items: deque[T] = deque()
        self._fut: deque[anyio.Event] = deque()

    def put_item(self, item: T):
        self._items.append(item)
        self._wakeup_first()

    def _wakeup_first(self):
        if self._fut and self._items:
            fut = self._fut.popleft()
            fut.set()

    async def get_item(self):
        if self._fut or not self._items:
            fut = anyio.Event()
            self._fut.append(fut)
            self._wakeup_first()
            await fut.wait()
        return self._items.popleft()

    def __len__(self):
        return len(self._items)

class Lock:
    def __init__(
        self,
    ):
        self._locked = False
        self._fut: deque[AnyioFuture] = deque()

    async def acquire(
        self,
    ):
        if not self._locked:
            self._locked = True
            return
        fut = AnyioFuture()
        self._fut.append(fut)
        try:
            await fut.wait()
        finally:
            self._fut.remove(fut)

    def release(
        self,
    ):
        if not self._locked or not self._fut:
            return
        fut = self._fut.popleft()
        fut.set_result(None)
        if not self._fut:
            self._locked = False

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        self.release()

class Event:
    def __init__(
        self
    ):
        self._fut: defaultdict[str, deque[AnyioFuture]] = defaultdict(deque)
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

def parse_tls_handshake(
    data: bytes
):
    version = 0
    sni = None
    try:
        buf = io.BytesIO(data)
        type = buf.read(1)[0]
        if type != 22:
            raise
        version = int.from_bytes(buf.read(2))
        # skip 40 bytes
        buf.read(40)
        buf.read(buf.read(1)[0])
        buf.read(int.from_bytes(buf.read(2), 'big'))
        buf.read(buf.read(1)[0])
        extensions_length = int.from_bytes(buf.read(2), 'big')
        current_extension_cur = 0
        while current_extension_cur < extensions_length:
            extension_type = int.from_bytes(buf.read(2), 'big')
            extension_length = int.from_bytes(buf.read(2), 'big')
            extension_data = buf.read(extension_length)
            if extension_type == 0x00: # SNI
                sni = extension_data[5:].decode("utf-8")
                break
            current_extension_cur += extension_length + 4
    except:
        return None

    return TLSHandshake(version, sni)

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

async def _gather(
    coro: Coroutine,
    results: dict[Coroutine, Any]
):
    results[coro] = await coro

async def gather(
    *coro: Coroutine
):
    results: dict[Coroutine, Any] = {}
    async with anyio.create_task_group() as task_group:
        for c in coro:
            task_group.start_soon(_gather, c, results)
    res = []
    for c in coro:
        res.append(results[c])
    return res

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
    def __init__(self, maxsize: Optional[int], ttl: float, timer=time.monotonic):
        cachetools.TTLCache.__init__(self, maxsize or math.inf, ttl, timer)

    @property
    def maxsize(self):
        return None

runtime = Runtime()
event = Event()