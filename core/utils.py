import asyncio
import base64
import binascii
from collections import deque
import collections
from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo
import functools
import hashlib
import io
import json
import os
from random import SystemRandom
import re
import struct
import threading
import time
from typing import Any, Optional, Tuple, Type, Union

from tqdm import tqdm

from core import scheduler
from core.logger import logger

class CountLock:
    def __init__(self):
        self.count = 0
        self.fut: deque[asyncio.Future] = deque()
    
    async def wait(self):
        if self.count >= 1:
            fut = asyncio.get_running_loop().create_future()
            self.fut.append(fut)
            try:
                await fut
            except asyncio.CancelledError:
                raise
            finally:
                if fut in self.fut:
                    self.fut.remove(fut)
    
    def acquire(self):
        self.count += 1
    
    def release(self):
        self.count -= 1
        if self.count == 0 and self.fut:
            self._wake()

    def _wake(self):
        if self.fut:
            for fut in self.fut:
                try:
                    fut.set_result(None)
                except asyncio.InvalidStateError:
                    pass
            self.fut.clear()

    @property
    def locked(self):
        return self.count > 0
    
class SemaphoreLock:
    def __init__(self, value: int):
        self._value = value
        self.count = 0
        self.fut: deque[asyncio.Future] = deque()
    
    async def wait(self):
        if self.count >= 1:
            fut = asyncio.get_running_loop().create_future()
            self.fut.append(fut)
            try:
                await fut
            except asyncio.CancelledError:
                raise
            finally:
                if fut in self.fut:
                    self.fut.remove(fut)
    
    async def acquire(self):
        if self.count >= self._value:
            await self.wait()
        self.count += 1
    
    def release(self):
        self.count -= 1
        if self.count == 0 and self.fut:
            self._wake()

    def _wake(self):
        if self.fut:
            for fut in self.fut:
                try:
                    fut.set_result(None)
                except asyncio.InvalidStateError:
                    pass
            self.fut.clear()

    @property
    def locked(self):
        return self.count > 0
    
    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
    
    def set_value(self, value: int):
        self._value = value  

class FileStream:
    def __init__(self, data: bytes) -> None:
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
    
class DataOutputStream(io.BytesIO):
    def write_long(self, value: int):
        value = (value << 1) ^ (value >> 63)
        while True:
            byte = value & 0x7F
            value >>= 7
            if value == 0:
                self.write(bytes([byte]))
                break
            else:
                self.write(bytes([byte | 0x80]))

    def write_string(self, value: str):
        try:
            data = value.encode('utf-8')
        except:
            logger.debug(f"encode error: {repr(value)}")
            data = value.encode('utf-8', errors='ignore')
        self.write_long(len(data))
        self.write(data)

class DataInputStream(io.BytesIO):

    def read_long(self): 
        result, shift = 0, 0
        while True:
            byte = ord(self.read(1))
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
        return (result >> 1) ^ -(result & 1)

    def read_string(self):
        return self.read(self.read_long()).decode('utf-8')

@dataclass
class Time:
    day: float = 0
    hour: float = 0
    minute: float = 0
    second: float = 0
    milisecond: float = 0

    @property
    def to_miliseconds(self):
        return self.day * 86400000 + self.hour * 3600000 + self.minute * 60000 + self.second * 1000 + self.milisecond
    @property
    def to_seconds(self):
        return self.day * 86400 + self.hour * 3600 + self.minute * 60 + self.second + self.milisecond / 1000
    @property
    def to_minutes(self):
        return self.day * 1440 + self.hour * 60 + self.minute + self.second / 60 + self.milisecond / 3600000
    @property
    def to_hours(self):
        return self.day * 24 + self.hour + self.minute / 60 + self.second / 3600 + self.milisecond / 3600000
    @property
    def to_days(self):
        return self.day + self.hour / 24 + self.minute / 1440 + self.second / 86400 + self.milisecond / 86400000

class WrapperTQDM:
    def __init__(self, pbar: tqdm):
        self.pbar = pbar
        self._rate = pbar.smoothing
        self.speed: deque[float] = deque(maxlen=int(1.0 / self._rate) * 30)
        self._n = pbar.n
        self._start = time.monotonic()
        self._time = time.monotonic()
        self._last_time = self._time
        self._counter = None
    
    def __enter__(self):
        wrapper_tqdms.appendleft(self)
        self._counter = threading.Thread(
            target=self._count,
        )
        self._counter.start()
        self.pbar.__enter__()
        return self
    
    def _count(self, sleep = True):
        while self._counter is not None:
            diff = (self.pbar.n - self._n) * (1.0 / ((time.monotonic() - self._last_time) or 1))
            self._last_time = time.monotonic()
            self._n = self.pbar.n
            self.speed.append(
                diff
            )
            if not sleep:
                continue
            time.sleep(self._rate)      
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self in wrapper_tqdms:
            wrapper_tqdms.remove(self)
        if self._counter:
            self._counter = None
        self._count(False)
        self.pbar.__exit__(exc_type, exc_val, exc_tb)

    def update(self, n: float | None = 1):
        self.pbar.update(n)
        if time.monotonic() - self._time > 1:
            self.speed.append(self.pbar.n / (time.monotonic() - self._time))
            self._time = time.monotonic()
        
    def set_postfix_str(self, s: str):
        self.pbar.set_postfix_str(s)

    def close(self):
        if self in wrapper_tqdms:
            wrapper_tqdms.remove(self)
        self.pbar.close()

    @property
    def start_time(self):
        return (self._start - get_start_runtime()) + (time.time() - get_runtime())

class Status:
    def __init__(
        self,
        key: str,
        **kwargs
    ):
        self.key = key
        self.timestamp = -1
        self.count = 0
        self.params = kwargs

    def __enter__(
        self,
    ):
        self.enter()
        return self
    
    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ):
        self.exit()
        
    def enter(
        self,
    ):
        self.count += 1
        if self in status_manager.status:
            return
        self.timestamp = time.monotonic()
        status_manager.status.appendleft(
            self
        )
        status_manager.lock.release()

    def exit(
        self,
    ):
        self.count -= 1
        if self.count > 0 or self not in status_manager.status:
            return
        self.timestamp = -1
        status_manager.status.remove(
            self
        )
        status_manager.lock.release()

class StatusManager:
    def __init__(
        self,
    ):
        self.status: deque[Status] = deque()
        self.lock = CountLock()

    async def wait(self):
        self.lock.acquire()
        await self.lock.wait()
        return self.status


    def get_current_status(
        self,
        sorted_by_timestamp: bool = False
    ):
        if sorted_by_timestamp:
            return sorted(self.status, key=lambda x: x.timestamp)
        return self.status

def check_sign(hash: str, secret: str, s: str, e: str) -> bool:
    return check_sign_without_time(hash, secret, s, e) and time.time() - 300 < int(e, 36)

def check_sign_without_time(hash: str, secret: str, s: str, e: str):
    if not s or not e:
        return False
    sign = (
        base64.urlsafe_b64encode(
            hashlib.sha1(f"{secret}{hash}{e}".encode()).digest()
        )
        .decode()
        .rstrip("=")
    )
    return sign == s

def equals_hash(origin: str, content: bytes):
    return get_hash_hexdigest(origin, content) == origin

def get_hash_hexdigest(origin: str, content: bytes):
    h = hashlib.sha1
    if len(origin) == 32:
        h = hashlib.md5
    return h(content).hexdigest()

def pause():
    try:
        input("Press Enter to continue...")
    except KeyboardInterrupt:
        exit()
        pass

def get_runtime():
    return time.monotonic() - get_start_runtime()

def get_start_runtime():
    from core import _START_RUNTIME
    return _START_RUNTIME

def parse_isotime_to_timestamp(iso_format: str) -> float:
    return datetime.fromisoformat(iso_format).timestamp()

def parse_gmttime_to_timestamp(gmt_format: str) -> float:
    return datetime.strptime(gmt_format, "%a, %d %b %Y %H:%M:%S %Z").timestamp()

def is_service_error(body: Any) -> bool:
    if isinstance(body, (bytes, str)):
        try:
            body = json.loads(body)
        except:
            return False
    return isinstance(body, dict) and "$isServiceError" in body and body["$isServiceError"]

def parse_service_error(body: Any) -> Optional['ServiceError']:
    if isinstance(body, (bytes, str)):
        try:
            body = json.loads(body)
        except:
            return None
    if not isinstance(body, dict) or "$isServiceError" not in body or not body["$isServiceError"]:
        return None
    return ServiceError(
        body["code"],
        body["httpCode"],
        body["message"],
        body["name"]
    )

def raise_service_error(body: Any, key: str = "utils.error.service_error", **kwargs) -> bool:
    service = parse_service_error(body)
    if service is None:
        return False
    logger.terror(key, code=service.code, httpCode=service.httpCode, message=service.message, name=service.name, **kwargs)
    return True

def parse_time(time_str: str):
    maps: dict[str, str] = {
        "ms": "milisecond",
        "s": "second",
        "m": "minute",
        "h": "hour",
        "d": "day"
    }
    obj = Time()
    parts = re.findall(r'(\d+(?:\.\d+)?)(ms|h|m|s|d)', time_str)
    for part in parts:
        value = float(part[0])
        unit = part[1]
        setattr(obj, maps[unit], value)
    return obj

async def run_sync(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)

@dataclass
class ServiceError:
    code: str
    httpCode: int
    message: str
    name: str

wrapper_tqdms: deque[WrapperTQDM] = deque()
status_manager: StatusManager = StatusManager()

def retry(max_retries: int = 3, delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        raise e
                    await asyncio.sleep(delay)
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        raise e
                    time.sleep(delay)
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator

_MAX_COUNTER_VALUE = 0xFFFFFF
_PACK_INT = struct.Struct(">I").pack
_PACK_INT_RANDOM = struct.Struct(">I5s").pack
_UNPACK_INT = struct.Struct(">I").unpack
def _raise_invalid_id(oid: str):
    raise ValueError(
        "%r is not a valid ObjectId, it must be a 12-byte input"
        " or a 24-character hex string" % oid
    )

def _random_bytes() -> bytes:
    """Get the 5-byte random field of an ObjectId."""
    return os.urandom(5)

class ObjectId:
    _pid = os.getpid()
    _inc = SystemRandom().randint(0, _MAX_COUNTER_VALUE)
    _inc_lock = threading.Lock()
    __random = _random_bytes()
    __slots__ = ("__id",)
    _type_marker = 7
    def __init__(self, oid: Optional[Union[str, 'ObjectId', bytes]] = None) -> None:
        if oid is None:
            self.__generate()
        elif isinstance(oid, bytes) and len(oid) == 12:
            self.__id = oid
        else:
            self.__validate(oid)
    @classmethod
    def from_datetime(cls: Type['ObjectId'], generation_time: datetime) -> 'ObjectId':
        oid = (
            _PACK_INT(generation_time.timestamp() // 1)
            + b"\x00\x00\x00\x00\x00\x00\x00\x00"
        )
        return cls(oid)
    @classmethod
    def is_valid(cls: Type['ObjectId'], oid: Any) -> bool:
        if not oid:
            return False
        try:
            ObjectId(oid)
            return True
        except (ValueError, TypeError):
            return False
    @classmethod
    def _random(cls) -> bytes:
        pid = os.getpid()
        if pid != cls._pid:
            cls._pid = pid
            cls.__random = _random_bytes()
        return cls.__random
    def __generate(self) -> None:
        with ObjectId._inc_lock:
            inc = ObjectId._inc
            ObjectId._inc = (inc + 1) % (_MAX_COUNTER_VALUE + 1)
        self.__id = _PACK_INT_RANDOM(int(time.time()), ObjectId._random()) + _PACK_INT(inc)[1:4]
    def __validate(self, oid: Any) -> None:
        if isinstance(oid, ObjectId):
            self.__id = oid.binary
        elif isinstance(oid, str):
            if len(oid) == 24:
                try:
                    self.__id = bytes.fromhex(oid)
                except (TypeError, ValueError):
                    _raise_invalid_id(oid)
            else:
                _raise_invalid_id(oid)
        else:
            raise TypeError(f"id must be an instance of (bytes, str, ObjectId), not {type(oid)}")
    @property
    def binary(self) -> bytes:
        return self.__id
    @property
    def generation_time(self) -> datetime:
        timestamp = _UNPACK_INT(self.__id[0:4])[0]
        return datetime.fromtimestamp(timestamp, utc)
    def __getstate__(self) -> bytes:
        return self.__id
    def __setstate__(self, value: Any) -> None:
        if isinstance(value, dict):
            oid = value["_ObjectId__id"]
        else:
            oid = value
        if isinstance(oid, str):
            self.__id = oid.encode("latin-1")
        else:
            self.__id = oid
    def __str__(self) -> str:
        return binascii.hexlify(self.__id).decode()
    def __repr__(self) -> str:
        return f"ObjectId('{self!s}')"
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ObjectId):
            return self.__id == other.binary
        return NotImplemented
    def __ne__(self, other: Any) -> bool:
        if isinstance(other, ObjectId):
            return self.__id != other.binary
        return NotImplemented
    def __lt__(self, other: Any) -> bool:
        if isinstance(other, ObjectId):
            return self.__id < other.binary
        return NotImplemented
    def __le__(self, other: Any) -> bool:
        if isinstance(other, ObjectId):
            return self.__id <= other.binary
        return NotImplemented
    def __gt__(self, other: Any) -> bool:
        if isinstance(other, ObjectId):
            return self.__id > other.binary
        return NotImplemented
    def __ge__(self, other: Any) -> bool:
        if isinstance(other, ObjectId):
            return self.__id >= other.binary
        return NotImplemented
    def __hash__(self) -> int:
        return hash(self.__id)

ZERO: timedelta = timedelta(0)

class FixedOffset(tzinfo):
    def __init__(self, offset: Union[float, timedelta], name: str) -> None:
        if isinstance(offset, timedelta):
            self.__offset = offset
        else:
            self.__offset = timedelta(minutes=offset)
        self.__name = name
    def __getinitargs__(self) -> Tuple[timedelta, str]:
        return self.__offset, self.__name
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__offset!r}, {self.__name!r})"
    def utcoffset(self, dt: Optional[datetime]) -> timedelta:
        return self.__offset
    def tzname(self, dt: Optional[datetime]) -> str:
        return self.__name
    def dst(self, dt: Optional[datetime]) -> timedelta:
        return ZERO

utc: FixedOffset = FixedOffset(0, "UTC")