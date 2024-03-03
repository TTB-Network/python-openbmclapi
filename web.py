import asyncio
import base64
from dataclasses import dataclass
import dataclasses
import datetime
from enum import Enum
import hashlib
import inspect
import io
import json
from mimetypes import guess_type
import os
from pathlib import Path
import re
import socket
import stat
import struct
import tempfile
import time
import traceback
import types
from typing import Any, Callable, Coroutine, Optional, Union, get_args
import typing
import zlib

import aiofiles
from Globals import BUFFER, status_codes

from utils import Client, error, fixedValue, get_data_content_type, info, parse_obj_as_type
from urllib import parse as urlparse
import utils
import Globals
import filetype

class Application:
    def __init__(self) -> None:
        global application
        application = self
        self.routes: list[Route] = []
        self.param_routes: list[Route] = []
        self.resources: dict[str, dict[str, Any]] = {}
        self.startups = []
        self.shutdowns = []
        self.started = False
        self.websockets: dict[str, list[WebSocket]] = {}
    async def start(self):
        if self.started:
            return
        self.started = True
        [asyncio.create_task(task() if inspect.iscoroutinefunction(task) else task) for task in self.startups]
    async def stop(self):
        if not self.started:
            return
        self.started = False
        [asyncio.create_task(task() if inspect.iscoroutinefunction(task) else task) for task in self.shutdowns]
    def startup(self):
        def decorator(f):
            self.startups.append(f)
            return f
        return decorator
    def shutdown(self):
        def decorator(f):
            self.shutdowns.append(f)
            return f
        return decorator
    def _add_route(self, path, method, f, ratelimit_seconds: float = 0, ratelimit_count: int = -1, ratelimit_func = None):
        route = Route(path, method, f, ratelimit_seconds=ratelimit_seconds, ratelimit_count=ratelimit_count, ratelimit_func=ratelimit_func)
        if route.params:
            self.param_routes.append(route)
            self.param_routes.sort(key=lambda route: route.raw_path.index("{"), reverse=True)
        else:
            self.routes.append(route)
    def route(self, path, method, host: str = '*', ratelimit_seconds: float = 0, ratelimit_count: int = -1, ratelimit_func = None):
        def decorator(f):
            self._add_route(path, method, f, ratelimit_seconds=ratelimit_seconds, ratelimit_count=ratelimit_count, ratelimit_func=ratelimit_func)
            return f
        return decorator
    async def handle(self, request: 'Request', client: Client):
        routes = filter(lambda route: route.method == request.method, [*self.routes, *self.param_routes])
        for route in routes:
            matched: tuple[bool, dict[str, Any]] = self.match_url(route, request.path)
            if matched[0]:
                params: dict[str, Any] = matched[1]
                url_params: dict[str, Any] = request.params
                has_set = []
                handler = route.handler if not route.is_limit(request=request) else (default_limit if route.get_limit_func() is None else route.get_limit_func())
                annotations = inspect.get_annotations(handler)
                default_params: dict[str, Any] = {name.lower(): value.default for name, value in inspect.signature(handler).parameters.items() if (not isinstance(value, inspect._empty)) and (value.default != inspect._empty)}
                request_params_lower = {**{k.lower(): v for k, v in request.params.items()}, **{k.lower(): v for k, v in url_params.items()}, **{k.lower(): v for k, v in params.items()}}
                request.parameters.update(request_params_lower)
                if not route.is_limit(request=request):
                    route.add_limit(request)
                for include_name, include_type in annotations.items():
                    include_name_lower = include_name.lower()
                    if include_type == Request:
                        params[include_name] = request
                        has_set.append(include_name_lower)
                    elif include_type == WebSocket and hasattr(request, "websocket"):
                        params[include_name] = request.websocket
                        has_set.append(include_name_lower)
                    elif include_type == RouteLimit:
                        params[include_name] = RouteLimit(request, route)
                        has_set.append(include_name_lower)
                    elif include_type == Form and hasattr(request, "form"):
                        params[include_name] = request.form
                        has_set.append(include_name_lower)
                    else:
                        param_lower = include_name_lower
                        if hasattr(request, 'json') and param_lower in request.json:
                            params[include_name] = parse_obj_as_type(request.json[param_lower], include_type)
                        elif param_lower in request_params_lower:
                            params[include_name] = request_params_lower[param_lower]
                        elif param_lower in default_params:
                            params[include_name] = default_params[param_lower]
                        elif hasattr(include_type, '__origin__') and include_type.__origin__ is Union and type(None) in get_args(include_type):
                            params[include_name] = None
                        try:
                            params[include_name] = parse_obj_as_type(params[include_name], include_type)
                            has_set.append(param_lower)
                        except:
                            yield await ErrorResponse.wrong_type_parameter(request.path, param=include_name, expected_type=include_type)
                            return
                if any(value.kind == value.VAR_KEYWORD for value in inspect.signature(handler).parameters.values()):
                    params.update(fixedValue({key: value for key, value in request_params_lower.items() if key not in has_set}))
                websocket = hasattr(request, "websocket")
                result: Any = None
                if websocket:
                    #waf.requestStatistics.add_request(request.address)
                    for resp in request.websocket.accept():
                        yield resp
                    if request.path not in self.websockets:
                        self.websockets[request.path] = []
                    self.websockets[request.path].append(request.websocket)
                    if inspect.iscoroutinefunction(handler):
                        await handler(**params)
                    else:
                        handler(**params)
                else:
                    try:
                        if inspect.iscoroutinefunction(handler):
                            result = await handler(**params)
                        else:
                            result = handler(**params)
                    except:
                        utils.traceback(True)
                        result = await ErrorResponse.internal_error(request.path)
                yield result
                return
        if self.resources:
            for key, value in self.resources.items():
                if request.path.startswith(key):
                    yield Response(Path(f"{value['url']}/{request.path[len(key):]}"), mount=(value, key))
                    return
        yield await ErrorResponse.not_found(request.raw_path)
        return

    def mount(self, path: str, source: str, show_dir = True):
        self.resources["/" + path.lstrip("/").lower()] = { 
            "url": source.replace("\\","/").rstrip("/"),
            "show_dir": show_dir
        }
    @staticmethod
    def match_url(target: 'Route', source: str) -> tuple[bool, dict[str, Any]]:
        params = {}
        if target.params:
            params = ([{name: r.group(name) for name in target.param} for rp in target.regexp if (r := rp.match(source))] or [{}])[0]
        return (source.lower() in target.path or bool(params), params)
    def get(self, path, ratelimit_seconds: float = 0, ratelimit_count: int = -1, ratelimit_func = None):
        return self.route(path, 'GET', ratelimit_seconds=ratelimit_seconds, ratelimit_count=ratelimit_count, ratelimit_func=ratelimit_func)
    def post(self, path, ratelimit_seconds: float = 0, ratelimit_count: int = -1, ratelimit_func = None):
        return self.route(path, 'POST', ratelimit_seconds=ratelimit_seconds, ratelimit_count=ratelimit_count, ratelimit_func=ratelimit_func)
    def delete(self, path, ratelimit_seconds: float = 0, ratelimit_count: int = -1, ratelimit_func = None):
        return self.route(path, 'DELETE', ratelimit_seconds=ratelimit_seconds, ratelimit_count=ratelimit_count, ratelimit_func=ratelimit_func)
    def websocket(self, path, ratelimit_seconds: float = 0, ratelimit_count: int = -1, ratelimit_func = None):
        return self.route(path, 'WebSocket', ratelimit_seconds=ratelimit_seconds, ratelimit_count=ratelimit_count, ratelimit_func=ratelimit_func)
    def get_websockets(self, path: str):
        if not path.startswith("/"):
            path = f'/{path}'
        path = path.replace("//", "/")
        return self.websockets.get(path, [])
class Route:
    def __init__(self, path: str, method: str, handler: Callable[..., Coroutine], ratelimit_seconds: float = 0, ratelimit_count: int = -1, ratelimit_func = None, host: Optional[str] = None, port: Optional[int] = None) -> None:
        self.raw_path = path
        self.path = (f'/{path.lstrip("/")}', f'/{path.lstrip("/")}/')
        self.handler = handler
        self.method = method or "GET"
        self.ratelimit = ratelimit_seconds != 0 and ratelimit_count >= 1
        self.params = self.is_params(path)
        if self.params:
            self.param = re.findall(r'{(\w+)}', path)
            self.regexp: list[re.Pattern] = [re.compile(rf"^{p.replace('{', '(?P<').replace('}', r'>[^/]*)')}$") for p in self.path]
        if self.ratelimit:
            self.ratelimit_configs = {
                "seconds": ratelimit_seconds,
                "count": ratelimit_count,
                "func": ratelimit_func,
            }
            self.ratelimit_cache = {}

    def is_params(self, path: str):
        return path.count("{") == path.count("}") != 0
    def __str__(self) -> str:
        return self.path[0]
    def get_limit_func(self):
        return self.ratelimit_configs['func']
    def is_limit(self, request: 'Request'):
        if not self.ratelimit:
            return False
        if request.address not in self.ratelimit_cache:
            self.ratelimit_cache[request.address] = {
                'count': 0,
                'seconds': 0
            }
        return self.ratelimit_cache[request.address]['count'] >= self.ratelimit_configs['count'] and self.ratelimit_cache[request.address]['seconds'] >= time.time()

    def add_limit(self, request: 'Request'):
        if not self.ratelimit:
            return
        if request.address not in self.ratelimit_cache:
            self.ratelimit_cache[request.address] = {
                'count': 0,
                'seconds': 0
            }
        if self.ratelimit_cache[request.address]['seconds'] < time.time():
            self.ratelimit_cache[request.address]['seconds'] = time.time() + self.ratelimit_configs['seconds']
        self.ratelimit_cache[request.address]['count'] += 1
    def get_limit(self, request: 'Request'):
        if request.address not in self.ratelimit_cache:
            self.ratelimit_cache[request.address] = {
                'count': 0,
                'seconds': 0
            }
        return self.ratelimit_cache[request.address]
class Request:
    async def __call__(self, data: bytes, client: Client) -> 'Request':
        if client.compressed:
            try: 
                data = zlib.decompress(data)
                data = await client.readuntil(b'\r\n\r\n', 30)
                data = zlib.decompress(data)
            except:
                ...
        if data.count(b"\r\n\r\n") == 0 and not client.compressed:
            data = await client.readuntil(b'\r\n\r\n', 30)
        elif data.count(b"\r\n\r\n") == 0 and client.compressed:
            raise EOFError
        (a := (b := data.split(b"\r\n\r\n", 1))[0].decode("utf-8").split("\r\n"))[1:]
        self.protocol = 'https' if client.get_server_port() == 443 or client.is_ssl else 'http'
        self.raw_header = {key: value for key, value in (b.split(": ") for b in a[1:])}
        self.method, self.raw_path = a[0].split(" ")[0:2]
        if self.method not in ('GET', 'POST'):
            raise ValueError("Method error")
        self.headers = {key.lower(): value for key, value in self.raw_header.items()}
        self.path = urlparse.unquote((url := urlparse.urlparse(self.raw_path)).path).replace("//", "/")
        self.params = {k: v[-1] for k, v in urlparse.parse_qs(url.query).items()}
        self.content_type = self.headers.get("content-type", None)
        self.address: str = client.get_ip()
        content_type = self.headers.get("content-type", None)
        self.user_agent: str = self.headers.get("user-agent", "")
        self.cookies = {}
        self.host: str = self.headers.get("host", "")
        self.port: int = 80
        self.parameters: dict[str, Any] = {}
        if '[' in self.host and ']' in self.host:
            self.port = int(self.host[self.host.find("]:") + 2:] if self.host.find("]:") != -1 else 80)
            self.host = socket.inet_ntoa(socket.inet_pton(socket.AF_INET6, self.host[1:self.host.find("]")])[-4:])
        else:
            r = self.host.split(":")
            self.host = r[0]
            self.port = int(r[1] if len(r) >= 2 else 80)
        self.authorization: Optional[str] = self.headers.get("authorization", None)
        if 'cookie' in self.headers:
            for cookie in self.headers['cookie'].split(';'):
                idx = cookie.find('=')
                if idx != -1:
                    k = cookie[:idx].strip()
                    v = cookie[idx+1:]
                    self.cookies[k] = v
        if 'connection' in self.headers and self.headers['connection'].lower() == "upgrade" and 'upgrade' in self.headers and self.headers['upgrade'].lower() == "websocket" and 'sec-websocket-version' in self.headers and self.headers['sec-websocket-version'] == '13':
            self.websocket = WebSocket(client=client, request=self)
            self.method = "WebSocket"
        client.unchecked = True
        self.length = int(self.headers.get("content-length", 0))
        if not content_type or self.length == 0:
            return self
        if self.method != "GET":
            if content_type.startswith("multipart/form-data"):
                self.boundary = content_type.split("; boundary=")[1]
                self.form = await FormParse.parse(self.boundary, client, self.length, b[1])
                return self
            else:
                self.content = tempfile.TemporaryFile()
                self.content.write(b[1])
                read_length = self.content.tell()
                while self.length != read_length:
                    data = await client.read(min(self.length - self.content.tell(), BUFFER), 30)
                    read_length += len(data)
                    await asyncio.get_event_loop().run_in_executor(None, self.content.write, data)
                self.content.seek(0)
        else:
            self.content = None
        if content_type.startswith("application/json"):
            self.json: dict[str, Any] = json.load(self.content or io.BytesIO())
            self.parameters.update(self.json)
        elif content_type.startswith("application/x-www-form-urlencoded"):
            self.json: dict[str, Any] = {k.decode("utf-8"): v[-1].decode("utf-8") for k, v in urlparse.parse_qs(self.content.read() if self.content else b'').items()}
            self.parameters.update(self.json)
        return self
    def __str__(self) -> str:
        return str({
            "length": self.length,
            "address": self.address,
            "method": self.method,
            "path": self.raw_path,
            "content-type": self.headers.get("content-type", None)
        })
    def __repr__(self) -> str:
        return self.__str__()
@dataclass
class Form:
    boundary: str
    files: dict[str, list[tempfile._TemporaryFileWrapper]]
    fields: dict[str, list[tempfile._TemporaryFileWrapper]]
class FormParse:
    @staticmethod
    async def parse(boundary_: str, client: Client, length: int, data: bytes) -> 'Form':
        boundary = b'\r\n--' + boundary_.encode("utf-8")
        if length == 0:
            return Form(boundary_, {}, {})
        files: dict[str, list[tempfile._TemporaryFileWrapper]] = {}
        fields: dict[str, list[tempfile._TemporaryFileWrapper]] = {}
        async def read_in_chunks(data: bytes):
            yield b'\r\n' + data
            read_length = len(data)
            while data := await client.read(min(length - read_length, BUFFER), 30):
                read_length += len(data)
                yield data
        def process_part(boundary: bytes, files: dict[str, list[tempfile._TemporaryFileWrapper]], fields: dict[str, list[tempfile._TemporaryFileWrapper]], part: bytes, temp_file): # type: ignore
            if b'\r\n\r\n' not in part:
                if temp_file:
                    temp_file.write(part.rstrip(boundary))
                return
            headers, body = part.split(b'\r\n\r\n', 1)
            headers = {key: value for key, value in ((urlparse.unquote(a.groupdict()['key']), urlparse.unquote(a.groupdict()['value'])) for a in re.finditer(r'(?P<key>\w+)="(?P<value>[^"\\]*(\\.[^"\\]*)*)"', headers.decode("utf-8")))}
            temp_file.write(body)
            if 'filename' in headers:
                if headers['filename'] not in files:
                    files[headers['filename']] = []
                files[headers['filename']].append(temp_file)
            if 'name' in headers:
                if headers['name'] not in fields:
                    fields[headers['name']] = []
                fields[headers['name']].append(temp_file)
        buffer = []
        temp_file = None
        async for chunk in read_in_chunks(data):
            buffer.append(chunk)
            while boundary in b''.join(buffer):
                t = [t for t in (b''.join(buffer)).split(boundary) if t]
                if temp_file != None:
                    process_part(boundary, files, fields, t[0], temp_file)
                    temp_file.seek(0)
                    temp_file = tempfile.TemporaryFile()
                    t = t[1:]
                part, tm = t[0], b'' if len(t) == 1 else boundary.join(t[1:])
                buffer = [tm]
                temp_file = tempfile.TemporaryFile()
                process_part(boundary, files, fields, part, temp_file)
            while len(buffer) >= 2 and temp_file != None:
                temp_file.write(b''.join(buffer[:-1]))
                buffer = buffer[-1:]
        process_part(boundary, files, fields, b''.join(buffer), temp_file)
        if temp_file:
            temp_file.seek(0) # type: ignore
        return Form(boundary_, files, fields)
class _StopIteration(Exception):
    ...
class OPCODE(Enum):
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA
class WebSocket:
    def __init__(self, client: Client, request: Request) -> None:
        self.client = client
        self.request = request
        self.__close = False
        self.stats = {
            "send": {
                "count": 0,
                "length": 0
            },
            "recv": {
                "count": 0,
                "length": 0
            }
        }
    def accept(self) -> Any:
        yield Response(headers={
            'Connection': 'Upgrade',
            'Upgrade': 'WebSocket',
            'Sec-WebSocket-Accept': base64.b64encode(hashlib.sha1(self.request.headers['sec-websocket-key'].encode('utf-8') + b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest()).decode('utf-8')
        }, status_code=101)
        self.keepalive = asyncio.create_task(self._ping())
        self.last_ping = False
        return
    async def _ping(self, ):
        try:
            while not self.__close:
                self.last_ping = True
                await self.send(b"", OPCODE.PING)
                await asyncio.sleep(5)
        except:
            error()
        self.__close = True
        await self.close()
    def is_closed(self, ) -> bool:
        return self.__close
    async def read_frame(self):
        data = await self.client.readexactly(2)
        head1, head2 = struct.unpack("!BB", data)
        fin  = bool(head1 & 0b10000000)
        mask = (head1 & 0x80) >> 7
        opcode = head1 & 0b00001111
        length = head2 & 0b01111111
        mask_bits = b''
        if length == 126:
            data = await self.client.readexactly(2)
            (length,) = struct.unpack("!H", data)
        elif length == 127:
            data = await self.client.readexactly(8)
            (length,) = struct.unpack("!Q", data)
        if mask:
            mask_bits = await self.client.readexactly(4)
        data = await self.client.readexactly(length)
        if (mask and mask_bits is None) or (mask and mask_bits and len(mask_bits) != 4):
            raise ValueError("mask must contain 4 bytes")
        if mask:
            data = bytes([data[i] ^ mask_bits[i % 4] for i in range(len(data))])
        if opcode == 8:
            if data:
                print(f"Closed reason: {data}")
            self.__close = True
            return opcode, data
        if not fin:
            c, d = await self.read_frame()
            if c != opcode:
                raise ValueError("opcode doesn't match {} {}".format(opcode, c))
            data += d
        return opcode, data
    async def read(self,) -> bytes:
        if self.__close:
            return b''
        try:
            code, payload = await self.read_frame()
            if code == OPCODE.PONG.value:
                return await self.read()
            if code == OPCODE.PING.value:
                await self.send(payload, OPCODE.PONG)
                return await self.read()
            if not (3 >= code >= 0):
                self.__close = True
                return b''
            self.stats["recv"]["count"] += 1
            self.stats["recv"]["length"] += len(payload)
            return payload
        except:
            self.__close = True
            return b''
    async def close(self, payload: Any | tuple = b'') -> int:
        if self.__close:
            return -1
        return await self.send(payload, OPCODE.CLOSE)
    async def keep(self):
        async for data in self.keepRead():
            if not data:
                break
    async def keepRead(self):
        while data := await self.read():
            if not data:
                break
            yield data
    async def __aiter__(self):
        while data := await self.read():
            if not data:
                break
            yield data
    async def send(self, payload: str | int | float | bool | list | dict | tuple | bytes | io.BytesIO | memoryview, opcode: Optional[OPCODE] = None):
        if isinstance(payload, (int, float, bool)):
            payload = str(payload)
        elif isinstance(payload, (list, dict, tuple)):
            payload = json.dumps(payload)
        elif isinstance(payload, bytes):
            payload = io.BytesIO(payload).getbuffer()
        elif isinstance(payload, io.BytesIO):
            payload = payload.getbuffer()
        if not opcode:
            if isinstance(payload, memoryview):
                opcode = OPCODE.BINARY
            else:
                opcode = OPCODE.TEXT
        if not isinstance(payload, memoryview) and isinstance(payload, str):
                payload = io.BytesIO(payload.encode("utf-8")).getbuffer()
        output = io.BytesIO()

        head1 = 0b10000000 | opcode.value
        head2 = 0
        length = len(payload)
        if length < 126:
            output.write(struct.pack("!BB", head1, head2 | length))
        elif length < 65536:
            output.write(struct.pack("!BBH", head1, head2 | 126, length))
        else:
            output.write(struct.pack("!BBQ", head1, head2 | 127, length))
        self.stats["send"]["count"] += 1
        self.stats["send"]["length"] += length
        output.write(payload)
        try:
            self.client.write(output.getvalue())
            if opcode == OPCODE.CLOSE:
                self.__close = True
            return length
        except:
            self.__close = True
            return -1

class Cookie:
    def __init__(self, key: str, value: str,
            expiry: Optional[float] = None,
            path: str = "/",
            maxAge: Optional[int] = None) -> None:
        self.key = key
        self.value = value
        self.expiry = expiry + time.time() + Globals.UTC if expiry else None
        self.path = (path if path else "")
        self.path = self.path if self.path.startswith("/") else "/" + self.path
        self.max_age = maxAge

    def __str__(self) -> str:
        return self.key + '=' + self.value + "; Path=" + self.path + ('; Expires=' + datetime.datetime.utcfromtimestamp(self.expiry).strftime('%a, %d %b %Y %H:%M:%S GMT') if self.expiry else '') + ("; Max-Age" if self.max_age else '')
class Response:
    def __init__(self, content: bytes | memoryview | str | None | Path | bool | typing.AsyncIterable | typing.Iterable | io.BytesIO | Any = b'', headers: dict[str, Any] = {}, status_code: int = 200, content_type: Optional[str] = None, cookie: list[Cookie] = [], **kwargs) -> None:
        self.headers: dict[str, Any] = Globals.default_headers.copy()
        self.headers["Date"] = datetime.datetime.fromtimestamp(time.time()).strftime("%a, %d %b %Y %H:%M:%S GMT")
        self.set_header(headers)
        self.set_header({
            'Content-Type': content_type or get_data_content_type(content)
        })
        self.set_content(content)
        self.status_code = status_code
        self.set_cookie(*cookie)
        self.kwargs = kwargs
    def set_header(self, headers: dict[str, Any] = {}):
        tmp_headers_index: dict[str, str] = {key.lower(): key for key in self.headers.keys()}
        for key, value in headers.items():
            if key.lower() not in ("server", "date", "content-length"):
                self.headers[tmp_headers_index.get(key.lower(), key)] = value
        return self
    def set_content(self, content: bytes | memoryview | str | None | Path | bool | typing.AsyncIterator | typing.Iterator | io.BytesIO | Any = b''):
        if isinstance(content, Path):
            content = Path(f"./{str(Path(str(content)))}")
        elif isinstance(content, io.BytesIO):
            content = content
        elif isinstance(content, (bytearray, bytes, memoryview)):
            content = io.BytesIO(content)
        elif isinstance(content, typing.Iterator):
            content = iterate_in_threadpool(content)
        self.content = content
    def set_cookie(self, *cookie):
        self.cookies = list(cookie)
        return self

    async def _iter(self):
        if isinstance(self.content, types.AsyncGeneratorType):
            async for data in self.content:
                yield data
        elif isinstance(self.content, (list, dict, tuple, set)) or None:
            try:
                content_type = content_type = list(set([key for key in self.headers.keys() if key.lower() == "content-type"] or ["Content-Type"]))[0]
                self.headers[content_type] = 'application/json'
                def aaa(array_: tuple | list | set):
                    array = list(array_)
                    for i, _ in enumerate(array):
                        if dataclasses.is_dataclass(_):
                            array[i] = dataclasses.asdict(_)
                    return array
                yield json.dumps(aaa(self.content) if isinstance(self.content, (list, tuple, set)) else self.content).encode('utf-8')
            except:
                utils.traceback()
                ...
        elif isinstance(self.content, (str, bool, int, float)):
            yield str(self.content).encode("utf-8")
        elif isinstance(self.content, Response):
            async for data in self.content._iter():
                print("aaa")
                yield data
        else:
            yield str(self.content).encode("utf-8")
            
    async def __call__(self, request: Request, client: Client, log: bool = True) -> Any:
        if client.is_closed():
            return
        content = io.BytesIO()
        length = 0
        keepalive = False
        if isinstance(self.content, io.BytesIO):
            content = self.content
            length = len(self.content.getbuffer())
            keepalive = True
        elif isinstance(self.content, Path) and self.content.is_file() and self.content.exists():
            content = self.content
            length = self.content.stat().st_size
            keepalive = True
        elif isinstance(self.content, Path) and not self.content.exists():
            self.status_code = 404
            self.content = await ErrorResponse.not_found(request.raw_path)
        if not keepalive and isinstance(content, io.BytesIO):
            try:
                async for data in self._iter():
                    content.write(data)
                length = content.tell()
            except:
                content = io.BytesIO()
                traceback.print_exc()
        tmp_headers = {key.lower(): key for key in self.headers.keys()}
        self.headers[tmp_headers.get("connection", "Connection")] = self.headers.get(tmp_headers.get("connection", "connection"), "Closed")
        start_bytes, end_bytes = 0, 0
        if isinstance(self.content, Path) and self.content.is_file():
            content_type = list(set([key for key in self.headers.keys() if key.lower() == "content-type"] or ["Content-Type"]))[0]
            self.headers[content_type] = filetype.guess_mime(self.content) or guess_type(self.content)[0] or 'text/plain' if isinstance(self.content, Path) and self.content.is_file() else 'text/plain'
        if keepalive and length >= Globals.BUFFER:
            range_str = request.headers.get('range', '')
            range_match = re.search(r'bytes=(\d+)-(\d+)', range_str, re.S) or re.search(r'bytes=(\d+)-', range_str, re.S)
            end_bytes = length - 1
            length = length - start_bytes if isinstance(self.content, Path) and self.content.is_file() and stat.S_ISREG(self.content.stat().st_mode) else length
            if range_match:
                start_bytes = int(range_match.group(1)) if range_match else 0
                if range_match.lastindex == 2:
                    end_bytes = int(range_match.group(2))
            self.set_header({
                'accept-ranges': 'bytes',
                'connection': 'keep-alive',
                'content-range': f'bytes {start_bytes}-{end_bytes}/{length}'
            })
            self.status_code = 206 if start_bytes > 0 else 200
            length = length - start_bytes
        self.headers["Content-Length"] = length
        set_cookie = '\r\n'.join(("Set-Cookie: " + str(cookie) for cookie in self.cookies))
        if set_cookie:
            set_cookie += '\r\n'
        tmp_header: str = "\r\n".join(f"{k}: {v}" for k, v in self.headers.items())
        if log:
            info(request.method, self.status_code, request.address, request.raw_path, request.user_agent)
        client.write(f'HTTP/1.1 {self.status_code} {status_codes.get(self.status_code, status_codes.get(self.status_code // 100 * 100))}\r\n{tmp_header}\r\n{set_cookie}\r\n'.encode("utf-8"))
        
        if isinstance(content, io.BytesIO):
            content.seek(start_bytes, os.SEEK_SET)
            client.write(content.getbuffer())
        elif isinstance(content, Path):
            async with aiofiles.open(content, "rb") as r:
                await r.seek(start_bytes, os.SEEK_SET)
                l = 0
                while (data := await r.read(min(BUFFER, length - l))) and l < length:
                    if not data:
                        break
                    l += len(data)
                    client.write(data)
                    await asyncio.sleep(0.1)
        if keepalive and length >= Globals.BUFFER:
            client.set_keepalive_connection(True)
class ErrorResponse:
    @staticmethod
    async def generate_error(path: str, description: str, status_code: int = 500, **kwargs) -> Response:
        error = {
            'path': path,
            'description': description,
        }
        error.update(**kwargs)
        return Response(error, status_code=status_code)

    @staticmethod
    async def missing_parameter(path: str, param: str, **kwargs) -> Response:
        return await ErrorResponse.generate_error(path, f'missing.parameter.{param}', **kwargs)

    @staticmethod
    async def invalid_parameter(path: str, param: str, **kwargs) -> Response:
        return await ErrorResponse.generate_error(path, f'invalid.parameter.{param}', **kwargs)

    @staticmethod
    async def wrong_type_parameter(path: str, param: str, expected_type: typing.Type, **kwargs) -> Response:
        if 'description' not in kwargs:
            kwargs['description'] = f'wrong.type.parameter.{param}.expected.{"integer" if expected_type == int else ("string" if expected_type == str else expected_type)}'
        return await ErrorResponse.generate_error(path, **kwargs)

    @staticmethod
    async def not_found(path: str, **kwargs) -> Response:
        return await ErrorResponse.generate_error(path, "not.found", 404, **kwargs)

    @staticmethod
    async def internal_error(path: str, **kwargs) -> Response:
        format_exc = traceback.format_exc()
        error(format_exc)
        return await ErrorResponse.generate_error(path, "internal.error", details=format_exc, **kwargs)
class RedirectResponse(Response):
    def __init__(self, url: str, query: dict[str, Any] = {}, **kwargs) -> None:
        path, params = url.split("?", 1) if '?' in url else (url, '')
        query.update({k: v[-1] for k, v in urlparse.parse_qs(urlparse.urlparse(f'?{params}').query).items()})
        super().__init__(headers={
            'location': path + ("?" + '&'.join([urlparse.quote(k.encode("utf-8")) + "=" + urlparse.quote(str(v).encode("utf-8")) for k, v in query.items()]) if query else '')
        }, status_code=307, **kwargs)
class RouteLimit:
    def __init__(self, request: 'Request', route: 'Route') -> None:
        self.value = route.get_limit(request)
        self.config = route.ratelimit_configs
    def __str__(self) -> str:
        return str(self.value)

application: Optional['Application'] = None
app = Application()
def default_limit(request: 'Request', route: 'RouteLimit'):
    return {
        "path": request.raw_path,
        "description": "ratelimit",
        "pastInSeconds": route.config['seconds'],
        "pastInRequests": route.config['count'],
    }
def _next(iterator: typing.Iterator):
    # We can't raise `StopIteration` from within the threadpool iterator
    # and catch it outside that context, so we coerce them into a different
    # exception type.
    try:
        return next(iterator)
    except StopIteration:
        raise _StopIteration
async def iterate_in_threadpool(iterator: typing.Iterator) -> typing.AsyncGenerator:
    while True:
        try:
            yield await anyio.to_thread.run_sync(_next, iterator) # type: ignore
        except _StopIteration:
            break
async def handle(data: bytes, client: Client):
    #client.set_log_network(waf.networkStatistics.add_network)
    #waf.networkStatistics.add_network(client, len(data), 0)
    request: Request = await Request()(data, client)
    #waf.requestStatistics.add_request(request.address)
    #type = waf.requestProtection.get_type(request.address, request.path)
    #if type == 3 or (type == 1 and bool(waf.Config.get("protection.request.enable", True))) or (type == 2 and bool(waf.Config.get("protection.attack.enable", True))):
        #waf.requestStatistics.add_denied(request.address)
    #    if request.raw_path.startswith("/check/"):
    #        passed = waf.requestProtection.check_key(request.address, request.raw_path.lstrip("/check/"))
    #        return await Response(status_code=430 if passed else 429)(request, client, False)
    #    #waf.requestProtection.add_request(request.address)
    #    await Response(waf.requestProtection.get_type_render(type).getvalue().replace(b'%key%', waf.requestProtection.create_key(request.address)).replace(b'%ip%', request.address.encode("utf-8")), content_type='text/html; charset=utf-8', status_code=429)(request, client, False)
    #    return
    #waf.requestProtection.add_request(request.address)
    #waf.requestProtection.add_path(request.path)
    results: int = 0
    try:
        if not application:
            await Response('The web server is not initization')(request, client)
        else:
            async for resp in application.handle(request, client):
                results += 1
                if not isinstance(resp, Response):
                    resp = Response(content=resp)
                await resp(request, client)
    except:
        utils.traceback(False)
        await Response(await ErrorResponse.internal_error(request.raw_path), status_code=500)(request, client)
        results += 1
    client.set_log_network(None)