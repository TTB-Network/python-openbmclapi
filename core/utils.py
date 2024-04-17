import asyncio
import base64
from dataclasses import asdict, dataclass, is_dataclass
import datetime
import hashlib
import inspect
import io
import os
import re
import time
from typing import (
    Any,
    Coroutine,
    AsyncGenerator,
    AsyncIterator,
    Callable,
    Generator,
    Iterable,
    Iterator,
    Optional,
    Type,
    Union,
    get_args,
)
import typing

from core.config import Config

bytes_unit = ["K", "M", "G", "T", "E"]


@dataclass
class Client:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    keepalive_connection: bool = False
    server_port: int = 0
    bytes_recv: int = 0
    bytes_sent: int = 0
    read_data: int = 0
    read_time: Optional[float] = None
    unchecked: bool = True
    log_network: Optional[Callable] = None
    compressed: bool = False
    is_ssl: bool = False
    peername: Optional[tuple[str, int]] = None
    sockname: Optional[tuple[str, int]] = None
    closed: bool = False
    min_rate: int = Config.get("advanced.min_rate")
    min_rate_timestamp: int = Config.get("advanced.min_rate_timestamp")
    timeout: int = Config.get("advanced.timeout")

    def is_proxy(self):
        return self.peername is not None

    def get_server_port(self):
        return self.server_port

    def invaild_ip(self):
        return self.writer.get_extra_info("peername") is None

    def _record_after(self, start_time: float, data) -> bytes:
        if self.unchecked:
            return data
        if not self.read_time:
            self.read_time = time.time()
        end_time = time.time() - start_time
        self.read_data += len(data)
        self.read_time += end_time
        speed = self.read_data / max(1, end_time)
        if speed < self.min_rate and self.read_time > self.min_rate_timestamp:
            raise TimeoutError("Data read speed is too low")
        return data

    async def readline(self, timeout: Optional[float] = timeout):
        start_time = time.time()
        data = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
        self.record_network(0, len(data))
        return self._record_after(start_time, data)

    async def readuntil(
        self,
        separator: bytes | bytearray | memoryview = b"\n",
        timeout: Optional[float] = timeout,
    ):
        if self.is_closed():
            return b""
        start_time = time.time()
        data = await asyncio.wait_for(
            self.reader.readuntil(separator=separator), timeout=timeout
        )
        self.record_network(0, len(data))
        return self._record_after(start_time, data)

    async def read(self, n: int = -1, timeout: Optional[float] = timeout):
        if self.is_closed():
            return b""
        start_time = time.time()
        data: bytes = await asyncio.wait_for(self.reader.read(n), timeout=timeout)
        self.record_network(0, len(data))
        return self._record_after(start_time, data)

    async def readexactly(self, n: int, timeout: Optional[float] = timeout):
        if self.is_closed():
            return b""
        start_time = time.time()
        data = await asyncio.wait_for(self.reader.readexactly(n), timeout=timeout)
        self.record_network(0, len(data))
        return self._record_after(start_time, data)

    def __aiter__(self):
        return self

    async def __anext__(self):
        val = await self.readline()
        if val == b"":
            raise StopAsyncIteration
        return val

    def get_address(self):
        return self.peername or self.writer.get_extra_info("peername")[:2]

    def get_sock_address(self):
        return self.sockname or self.writer.get_extra_info("sockname")[:2]

    def get_ip(self):
        return self.get_address()[0]

    def get_port(self):
        return self.get_address()[1]

    def write(self, data: bytes | bytearray | memoryview):
        if self.is_closed():
            return -1
        try:
            self.writer.write(data)
            length: int = len(data)
            self.record_network(length, 0)
            return length
        except:
            self.close()
        return -1

    def writelines(self, data: Iterable[bytes | bytearray | memoryview]):
        if self.is_closed():
            return -1
        try:
            self.writer.writelines(data)
            length: int = sum([len(raw_data) for raw_data in data])
            self.record_network(length, 0)
            return length
        except:
            self.close()
        return -1

    def set_keepalive_connection(self, value: bool):
        self.keepalive_connection = value

    def close(self):
        if self.closed or self.is_closed():
            return
        self.closed = True
        self.writer.transport.abort()
        return self.writer.close()

    def is_closed(self):
        return self.closed or self.writer.is_closing()

    def set_log_network(self, handler):
        self.log_network = handler

    def record_network(self, sent: int, recv: int):
        if not self.log_network:
            return
        self.log_network(sent, recv)


class WaitLock:
    def __init__(self) -> None:
        self.waiters: list[asyncio.Future] = []
        self.locked = False
    def acquire(self):
        if self.locked:
            return
        self.locked = True
    def release(self):
        if not self.locked:
            return
        self.locked = False
        for waiter in self.waiters:
            waiter.set_result(True)
        self.waiters.clear()
    async def wait(self):
        if not self.locked:
            return
        fut = asyncio.get_running_loop().create_future()
        self.waiters.append(fut)
        try:
            await fut
        except:
            ...
        
        



def parse_obj_as_type(obj: Any, type_: Type[Any]) -> Any:
    if obj is None:
        return obj
    origin = getattr(type_, "__origin__", None)
    args = get_args(type_)
    if origin == Union:
        for arg in args:
            try:
                return parse_obj_as_type(obj, getattr(arg, "__origin__", arg))
            except:
                ...
        return None
    elif origin == dict:
        for arg in args:
            try:
                return parse_obj_as_type(obj, getattr(arg, "__origin__", arg))
            except:
                ...
        return load_params(obj, origin)
    elif origin == inspect._empty:
        return None
    elif origin == list:
        for arg in args:
            try:
                return [
                    parse_obj_as_type(o, getattr(arg, "__origin__", arg)) for o in obj
                ]
            except:
                ...
        return []
    elif origin is not None:
        return origin(obj)
    else:
        for arg in args:
            try:
                return parse_obj_as_type(obj, getattr(arg, "__origin__", arg))
            except:
                return arg(**load_params(obj, type_))
    try:
        return type_(**load_params(obj, type_))
    except:
        try:
            return load_params(obj, type_)
        except:
            return type_(obj)


def load_params(data: Any, type_: Any):
    value = {
        name: (value.default if value.default is not inspect._empty else None)
        for name, value in inspect.signature(type_).parameters.items()
        if not isinstance(value, inspect._empty)
    }
    if isinstance(data, dict):
        for k, v in data.items():
            value[k] = v
        return value
    else:
        return data


def fixedValue(data: dict[str, Any]):
    for key, value in data.items():
        if value.lower() == "true":
            data[key] = True
        elif value.lower() == "false":
            data[key] = False
        elif value.isdigit():
            data[key] = int(value)
        else:
            try:
                data[key] = float(value)
            except ValueError:
                pass
    return data


def parseObject(data: Any):
    if isinstance(data, dict):
        for k, v in data.items():
            data[k] = parseObject(v)
    elif isinstance(data, (tuple, list)):
        data = [parseObject(d) for d in data]
    elif is_dataclass(data):
        data = asdict(data)
    return data


def parse_iso_time(text: str):
    return datetime.datetime.fromisoformat(text)


def parse_datetime_to_gmt(date: time.struct_time):
    return f"{date.tm_year:04d}:{date.tm_mon:02d}:{date.tm_mday:02d} {date.tm_hour:02d}:{date.tm_min:02d}:{date.tm_sec:02d}"


def parse_time_to_gmt(time_: float):
    return parse_datetime_to_gmt(datetime.datetime.fromtimestamp(time_).utctimetuple())


CONTENT_ACCEPT = Union[
    io.BytesIO,
    memoryview,
    bytes,
    int,
    float,
    str,
    bool,
    dict,
    tuple,
    list,
    set,
    AsyncIterator,
    AsyncGenerator,
    Iterator,
    Coroutine,
    Generator,
    None,
]
WEBSOCKETCONTENT = Union[
    str
    | dict
    | list
    | tuple
    | set
    | bytes
    | memoryview
    | io.BytesIO
    | AsyncGenerator
    | AsyncIterator
    | Iterator
    | Generator,
    None,
]


class _StopIteration(Exception): ...


def content_next(iterator: typing.Iterator):
    try:
        return next(iterator)
    except StopIteration:
        raise _StopIteration


def get_timestamp_from_day(day: int):
    t = int(time.time())
    return t - (t - time.timezone) % 86400 - 86400 * day


def get_timestamp_from_day_tohour(day: int):
    t = int(time.time())
    return (t - (t - time.timezone) % 86400 - 86400 * day) / 3600


def get_timestamp_from_hour_tohour(hour: int):
    t = int(time.time())
    return (t - (t - time.timezone) % 3600 - 3600 * hour) / 3600

def get_timestamp_from_day_today(day: int):
    t = int(time.time())
    return (t - (t - time.timezone) % 86400 - 86400 * day) / 86400


def calc_bytes(v):
    unit = bytes_unit[0]
    for units in bytes_unit:
        if abs(v) >= 1024.0:
            v /= 1024.0
            unit = units
    return f"{v:.2f} {unit}iB"


def calc_more_bytes(*values):
    v = min(*values)
    unit = bytes_unit[0]
    i = 0
    for units in bytes_unit:
        if abs(v) >= 1024.0:
            v /= 1024.0
            i += 1
            unit = units
    return [f"{(v / (1024.0 ** i)):.2f} {unit}iB" for v in values]


def calc_bit(v):
    unit = bytes_unit[0]
    v *= 8
    for units in bytes_unit:
        if abs(v) >= 1024.0:
            v /= 1024.0
            unit = units
    return f"{v:.2f} {unit}bps"


def calc_more_bit(*values):
    v = min(*values) * 8
    unit = bytes_unit[0]
    i = 0
    for units in bytes_unit:
        if abs(v) >= 1024.0:
            v /= 1024
            i += 1
            unit = units
    return [f"{(v * 8 / (1024.0 ** i)):.2f} {unit}bps" for v in values]


def updateDict(dict: dict, new: dict):
    org = dict.copy()
    org.update(new)
    return org


def format_stime(n):
    if not n:
        return "--:--:--"
    n = int(n)
    hour = int(n / 60 / 60)
    minutes = int(n / 60 % 60)
    second = int(n % 60)
    return f"{hour:02d}:{minutes:02d}:{second:02d}"


def format_time(k: float):
    local = time.localtime(k)
    return f"{local.tm_hour:02d}:{local.tm_min:02d}:{local.tm_sec:02d}"


def format_date(k: float):
    local = time.localtime(k)
    return f"{local.tm_year:04d}-{local.tm_mon:02d}-{local.tm_mday:02d}"


def get_env_monotonic():
    return float(os.environ.get("MONOTONIC"))

def get_uptime():
    return time.monotonic() - get_env_monotonic()


def base36_encode(number):
    num_str = "0123456789abcdefghijklmnopqrstuvwxyz"
    if number == 0:
        return "0"

    base36 = []
    while number != 0:
        number, i = divmod(number, 36)  # 返回 number// 36 , number%36
        base36.append(num_str[i])

    return "".join(reversed(base36))


def parse_cache_control(cache_control_header: str):
    directives = {}
    # 使用正则表达式匹配指令和值
    matches = re.findall(r'(\w+)\s*=\s*(".*?"|[^,;]+)?', cache_control_header)
    for directive, value in matches:
        # 去除引号（如果有的话）
        if value and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        directives[directive.lower()] = value
    return directives


def check_sign(hash: str, secret: str, s: str, e: str) -> bool:
    try:
        t = int(e, 36)
    except:
        return False
    sha1 = hashlib.sha1()
    sha1.update(secret.encode("utf-8"))
    sha1.update(hash.encode("utf-8"))
    sha1.update(e.encode("utf-8"))
    return (
        base64.urlsafe_b64encode(sha1.digest()).decode().strip("=") == s
        and time.time() * 1000 <= t
    )


class MinecraftUtils:
    @staticmethod
    def getVarInt(data: int):
        r: bytes = b""
        while 1:
            if data & 0xFFFFFF80 == 0:
                r += data.to_bytes(1, "big")
                break
            r += (data & 0x7F | 0x80).to_bytes(1, "big")
            data >>= 7
        return r

    @staticmethod
    def getVarIntLength(data: int):
        return len(MinecraftUtils.getVarInt(data))


class DataOutputStream:
    def __init__(self, encoding: str = "utf-8") -> None:
        self.io = io.BytesIO()
        self.encoding = encoding

    def write(self, value: bytes | int):
        if isinstance(value, bytes):
            self.io.write(value)
        else:
            self.io.write((value + 256 if value < 0 else value).to_bytes(1, "big"))  # type: ignore

    def writeBoolean(self, value: bool):
        self.write(value.to_bytes(1, "big"))

    def writeShort(self, data: int):
        self.write(((data >> 8) & 0xFF).to_bytes(1, "big"))
        self.write(((data >> 0) & 0xFF).to_bytes(1, "big"))

    def writeInteger(self, data: int):
        self.write(((data >> 24) & 0xFF).to_bytes(1, "big"))
        self.write(((data >> 16) & 0xFF).to_bytes(1, "big"))
        self.write(((data >> 8) & 0xFF).to_bytes(1, "big"))
        self.write((data & 0xFF).to_bytes(1, "big"))

    def writeVarInt(self, value: int):
        self.write(MinecraftUtils.getVarInt(value))

    def writeString(self, data: str, encoding: Optional[str] = None):
        self.writeVarInt(len(data.encode(encoding or self.encoding)))
        self.write(data.encode(encoding or self.encoding))

    def writeLong(self, data: int):
        data = data - 2**64 if data > 2**63 - 1 else data
        self.write((data >> 56) & 0xFF)
        self.write((data >> 48) & 0xFF)
        self.write((data >> 40) & 0xFF)
        self.write((data >> 32) & 0xFF)
        self.write((data >> 24) & 0xFF)
        self.write((data >> 16) & 0xFF)
        self.write((data >> 8) & 0xFF)
        self.write((data >> 0) & 0xFF)

    def __sizeof__(self) -> int:
        return self.io.tell()

    def __len__(self) -> int:
        return self.io.tell()


class DataInputStream:
    def __init__(self, initial_bytes: bytes = b"", encoding: str = "utf-8") -> None:
        self.io = io.BytesIO(initial_bytes)
        self.encoding = encoding

    def read(self, __size: int | None = None):
        return self.io.read(__size)

    def readIntegetr(self):
        value = self.read(4)
        return (value[0] << 24) + (value[1] << 16) + (value[2] << 8) + (value[3] << 0)

    def readBoolean(self):
        return bool(int.from_bytes(self.read(1), byteorder="big"))

    def readShort(self):
        value = self.read(2)
        if value[0] | value[1] < 0:
            raise EOFError()
        return (value[0] << 8) + (value[1] << 0)

    def readLong(self) -> int:
        value = list(self.read(8))
        value = (
            (value[0] << 56)
            + ((value[1] & 255) << 48)
            + ((value[2] & 255) << 40)
            + ((value[3] & 255) << 32)
            + ((value[4] & 255) << 24)
            + ((value[5] & 255) << 16)
            + ((value[6] & 255) << 8)
            + ((value[7] & 255) << 0)
        )
        return value - 2**64 if value > 2**63 - 1 else value

    def readVarInt(self) -> int:
        i: int = 0
        j: int = 0
        k: int
        while 1:
            k = int.from_bytes(self.read(1), byteorder="big")
            i |= (k & 0x7F) << j * 7
            j += 1
            if (k & 0x80) != 128:
                break
        return i

    def readString(
        self, maximun: Optional[int] = None, encoding: Optional[str] = None
    ) -> str:
        return self.read(
            self.readVarInt()
            if maximun is None
            else min(self.readVarInt(), max(maximun, 0))
        ).decode(encoding or self.encoding)

    def readBytes(self, length: int) -> bytes:
        return self.read(length)


class FileDataInputStream(DataInputStream):
    def __init__(self, br: io.BufferedReader) -> None:
        super().__init__()
        self.io = br

    def read(self, __size: int | None = None):
        data = self.io.read(__size)
        if not data:
            raise EOFError(self.io)
        return data


class FileDataOutputStream(DataOutputStream):
    def __init__(self, bw: io.BufferedWriter) -> None:
        super().__init__()
        self.io = bw
