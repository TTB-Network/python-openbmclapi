import asyncio
import base64
from collections import deque
from dataclasses import dataclass
from datetime import datetime
import functools
import hashlib
import io
import json
import re
import time
from typing import Any, Optional

from core import logger


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


def check_sign(hash: str, secret: str, s: str, e: str) -> bool:
    return check_sign(hash, secret, s, e) and time.time() - 300 < int(e, 36)

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
    from core import _START_RUNTIME
    return time.monotonic() - _START_RUNTIME

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
