import asyncio
from dataclasses import dataclass
import datetime
import inspect
import io
import json
from mimetypes import guess_type
from pathlib import Path
import re
import tempfile
import time
import traceback
from typing import Any, AsyncGenerator, AsyncIterator, Callable, Coroutine, Generator, Iterator, Optional, Union, get_args

import aiofiles
from utils import CONTENT_ACCEPT, Client, content_next, parse_obj_as_type
import config
import filetype
import urllib.parse as urlparse


class Route:
    def __init__(self, path: str, method: Optional[str], handler: Callable[..., Coroutine]) -> None:
        self._path = (path if path.startswith("/") else "/" + path)
        self._params = path.count("{") == path.count("}") != 0
        self.handler = handler
        self.method = method or "GET"
        if self._params:
            self.param = re.findall(r'{(\w+)}', path)
            self.regexp: re.Pattern = re.compile(rf"^{path.replace('{', '(?P<').replace('}', r'>[^/]*)')}$")
    def is_params(self):
        return self._params

class Router:
    def __init__(self, prefix: str = "", *routes: Route) -> None:
        self.prefix = (prefix if prefix.startswith("/") else "/" + prefix) if prefix else ""
        self._routes: dict[str, list[Route]] = {method: [] for method in ("GET", "POST", "PUT", "DELETE")}
        self.add(*routes)
    def add(self, *routes: Route) -> None:
        for route in routes:
            if route.method not in self._routes:
                self._routes[route.method] = []
            if route._params:
                self._routes[route.method].insert(0, route)
            else:
                self._routes[route.method].append(route)
    def get_route(self, method: str, url: str) -> Optional[Route]:
        url = url.removeprefix(self.prefix)
        for route in self._routes[method]:
            if  route.is_params() and route.regexp.match(url) or route._path == url:
                return route
        return None
    def route(self, path: str, method):
        def decorator(f):
            self._add_route(Route(path, method, f))
            return f
        return decorator
    def _add_route(self, route: Route):
        if route.method not in self._routes:
            self._routes[route.method] = []
        if route.is_params():
            self._routes[route.method].insert(0, route)
        else:
            self._routes[route.method].append(route)
    def get(self, path):
        return self.route(path, 'GET')
    def post(self, path):
        return self.route(path, 'POST')
        
class Resource:
    def __init__(self, path: Path, show_dir: bool = False) -> None:
        if not path.is_dir():
            raise RuntimeError(f"The path {path} is not dir.")
        self.dir = path.absolute()
    def get_files(self):
        ...

class Application:
    def __init__(self) -> None:
        self._routes: list[Router] = [Router()]
    def route(self, path: str, method):
        def decorator(f):
            self._add_route(Route(path, method, f))
            return f
        return decorator
    def _add_route(self, route: Route):
        self._routes[0].add(route)
    def get(self, path):
        return self.route(path, 'GET')
    def post(self, path):
        return self.route(path, 'POST')
    async def handle(self, request: 'Request', client: Client):
        cur_route = None
        method = await request.get_method()
        url = request.get_url()
        for route in self._routes:
            cur_route = route.get_route(method, url)
            if cur_route:
                break
        result = None
        if cur_route != None:
            handler = cur_route.handler
            url_params: dict[str, Any] = {}#([{name: r.group(name) for name in cur_route.param}(r := cur_route.regexp.match(request.get_url()))] or [{}])[0] if cur_route.params else {}
            if cur_route.is_params():
                r = cur_route.regexp.match(request.get_url())
                if r:
                    url_params.update({name: r.group(name) for name in cur_route.param})
            annotations = inspect.get_annotations(handler)
            default_params: dict[str, Any] = {name.lower(): value.default for name, value in inspect.signature(handler).parameters.items() if (not isinstance(value, inspect._empty)) and (value.default != inspect._empty)}
            params = {}
            sets = []
            is_json = await request.is_json()
            json = await request.json() or {} if is_json else {}
            for include_name, include_type in annotations.items():
                if include_type == Request:
                    params[include_name] = request
                    sets.append(include_name)
                elif include_type == Form and request.is_form():
                    params[include_name] = request.form()
                    sets.append(include_name)
                else:
                    if include_name in url_params:
                        params[include_name] = url_params[include_name]
                    elif include_name in request.params:
                        params[include_name] = request.params[include_name]
                    elif is_json and include_name in json:
                        params[include_name] = json[include_name]
                    elif include_name in default_params:
                        params[include_name] = default_params[include_name]
                    elif hasattr(include_type, '__origin__') and include_type.__origin__ is Union and type(None) in get_args(include_type):
                        params[include_name] = None
                    try:
                        params[include_name] = parse_obj_as_type(params[include_name], include_type)
                        sets.append(include_name)
                    except:
                        traceback.print_exc()
                        return
            try:
                if inspect.iscoroutinefunction(handler):
                    result = await handler(**params)
                else:
                    result = handler(**params)
            except:
                traceback.print_exc()

        await Response(content=result or '', headers=Header({ # type: ignore
            "Server": "TTB-Network"
        }))(request, client)
    def mount(self, router: Router):
        self._routes.append(router)

class Cookie:
    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value
    def __str__(self) -> str:
        return "{}={}".format(
            self.key,
            self.value
        )

class Header:
    def __init__(self, header: dict[str, Any] | bytes | str | None = None) -> None:
        self._headers = {}
        if isinstance(header, bytes):
            self._headers.update({v[0]: v[1] for v in (v.split(": ") for v in header.decode(config.ENCODING).split("\r\n") if v.strip())})
        elif isinstance(header, str):
            self._headers.update({v[0]: v[1] for v in (v.split(": ") for v in header.split("\r\n") if v.strip())})
        elif isinstance(header, dict):
            self._headers.update(header)
    def get(self, key: str, def_ = None) -> Any:
        return self._headers.get(self._parse_key(key), def_)
    def set(self, key: str, value: Any) -> None:
        org_key = self._parse_key(key)
        if org_key in self._headers:
            self._headers.pop(self._parse_key(key))
        self._headers[key] = value
    def _parse_key(self, key: str) -> str:
        keys = list(self._headers.keys())
        lkeys = list(map(str.lower, keys))
        return keys[lkeys.index(key.lower())] if key.lower() in lkeys else key
    def update(self, value: Any):
        if isinstance(value, Header):
            value = value._headers
        if not isinstance(value, dict):
            return
        for k, v in value.items():
            self.set(k, v)
    def __str__(self) -> str:
        return '\r\n'.join(
            ("{}: {}".format(k, v) for k, v in self._headers.items())
        )
    def __len__(self) -> int:
        return self._headers.keys().__len__()

class Response:
    def __init__(self, content: CONTENT_ACCEPT = None, headers: Header = Header(), cookies: dict[str, Any] = {}, content_type: Optional[str] = None, compress = None, status_code: int = 200) -> None:
        self.status_code = status_code
        self.content: CONTENT_ACCEPT = content
        self._headers = headers
        self._cookies = cookies
        self.content_type = content_type
        self._compress = compress
    def set_headers(self, header: Header | dict[str, Any]):
        self._headers.update(header)
    def _get_content_type(self):
        if isinstance(self.content, (AsyncGenerator, Iterator, AsyncIterator, Generator)):
            return "bytes"
        content = self.content_type or filetype.guess_mime(self.content) or (guess_type(self.content)[0] if isinstance(self.content, Path) and self.content.exists() and self.content.is_file() else "text/plain") or "text/plain"
        content = content.lower()
        if content in ("text/plain", "application/javascript", ):
            content += f"; {config.ENCODING}"
        return content
    async def _iter(self):
        if isinstance(self.content, (str, int, float)):
            yield str(self.content).encode(config.ENCODING)
        elif isinstance(self.content, (dict, list, tuple, bool)):
            self.content_type = "application/json"
            yield json.dumps(self.content).encode(config.ENCODING)
        elif isinstance(self.content, (Iterator, Generator)):
            async for data in content_next(self.content): # type: ignore
                yield data
        elif isinstance(self.content, (AsyncIterator, AsyncGenerator)):
            async for data in self.content:
                yield data
        else:
            yield b''
    async def __call__(self, request: 'Request', client: Client) -> Any:
        content, length = io.BytesIO(), 0
        if isinstance(self.content, Response):
            self.content_type = self.content.content_type
            self.content = self.content.content
        if isinstance(self.content, Path):
            if self.content.exists() and self.content.is_file(): content = self.content
        elif isinstance(self.content, (memoryview, bytearray, bytes)):
            content = io.BytesIO(self.content)
            self.content_type = "bytes"
        elif isinstance(self.content, io.BytesIO): content = self.content
        else:
            async for data in self._iter():
                content.write(data)
        if isinstance(content, Path): length = content.stat().st_size
        else: length = len(content.getbuffer())
        self.set_headers(
            {**config.RESPONSE_HEADERS,
                "Date": datetime.datetime.fromtimestamp(time.time()).strftime(config.RESPONSE_DATE),
                "Content-Length": length, 
                "Connection": "Upgrade" if self.status_code == 101 else await request.get_headers("Connection") or "Closed",
                "Content-Type": self._get_content_type(),
            }
        )
        headers, cookie = '', ''
        if self._headers: headers = str(self._headers) + "\r\n"
        request._end_request_time(self.status_code)
        header = f'{request.protocol} {self.status_code} {config.status_codes[self.status_code] if self.status_code in config.status_codes else config.status_codes[self.status_code // 100 * 100]}\r\n{headers}{cookie}\r\n'.encode(config.ENCODING)
        client.write(header)
        if length != 0:
            if isinstance(content, io.BytesIO): 
                client.write(content.getbuffer())
            else:
                async with aiofiles.open(content, "rb") as r:
                    cur_length: int = 0
                    while (data := await r.read(min(config.IO_BUFFER, length - cur_length))):
                        cur_length += len(data)
                        client.write(data)
        if (self._headers.get("Connection") or "Closed").lower() == "closed":
            client.close()

class Request:
    def __init__(self, data: bytes, client: Client):
        self._start = time.time_ns()
        self._end = None
        self._status_code = None
        self._ip = client.get_ip()
        self._user_agent = None
        self.client = client
        self.method, self.url, self.protocol = data.decode(config.ENCODING).strip().split(" ")
        self.path = urlparse.unquote((url := urlparse.urlparse(self.url)).path).replace("//", "/")
        self.params = {k: v[-1] for k, v in urlparse.parse_qs(url.query).items()}
        self.parameters: dict[str, str] = {}
        self._headers = {}
        self._read_content = False
        self._length = 0
        self._read_length = 0
        self._check_websocket = False
        self._json = None
        self._form = None
    def get_url(self):
        return self.path
    def get_ip(self):
        return self._ip
    def get_user_agent(self):
        return self._user_agent or ""
    async def get_method(self):
        if not self._check_websocket and self.method == "GET" and (await self.get_headers("Connection") or "Closed") == "WebSocket":
            self.method = "WebSocket"
        return self.method
    async def get_headers(self, key: str, def_ = None):
        if not self._headers:
            self._headers = Header(await self.client.readuntil(b"\r\n\r\n"))
            self._user_agent = self._headers.get("user-agent")
        return self._headers.get(key.lower(), def_)
    async def length(self):
        return int(await self.get_headers("content-length", "0") or "0")
    async def content_iter(self, buffer: int = config.IO_BUFFER):
        if self._read_content:
            return
        self._length = int(await self.get_headers("content-length", "0") or "0")
        self._read_content = True
        while (data := await self.client.read(min(buffer, self._length - self._read_length))) and self._read_length < self._length:
            self._read_length += len(data)
            yield data
    async def skip(self):
        if self._read_length and self._length == self._read_length:
            return
        async for data in self.content_iter():
            ...
    def _end_request_time(self, status_code):
        self._end = time.time_ns() - self._start
        self._status_code = status_code
    def get_request_time(self):
        if self._end is None:
            return "-".rjust(16, " ")
        v = self._end
        units = config.REQUEST_TIME_UNITS[0]
        for unit in config.REQUEST_TIME_UNITS:
            if v >= 1000:
                v /= 1000 
                units = unit
        return f"{v:.4f}{units.ljust(2)}".rjust(14, " ")
    def get_status_code(self):
        return self._status_code or "-"
    async def is_form(self):
        content_type = await self.get_headers("Content-Type") or ""
        return self.method != "GET" and (content_type).startswith("multipart/form-data")
    async def form(self):
        content_type: str = await self.get_headers("Content-Type") or ""
        if self.method != "GET" or not (content_type).startswith("multipart/form-data") or self._form:
            return self._form
        boundary = content_type.split("; boundary=")[1]
        self._form = await FormParse.parse(boundary, self.content_iter, await self.length())
        return self._form
    async def is_json(self):
        content_type: str = await self.get_headers("Content-Type") or ""
        return content_type.startswith("application/json") or content_type.startswith("application/x-www-form-urlencoded")
    async def json(self):
        content_type: str = await self.get_headers("Content-Type") or ""
        if not (content_type.startswith("application/json") or content_type.startswith("application/x-www-form-urlencoded")) or self._json:
            return self._json
        buf = io.BytesIO()
        async for data in self.content_iter():
            buf.write(data)
        if content_type.startswith("application/json"):
            self._json = json.load(buf)
        elif content_type.startswith("application/x-www-form-urlencoded"):
            self._json = {k.decode("utf-8"): v[-1].decode("utf-8") for k, v in urlparse.parse_qs(buf.getvalue()).items()}
        return self._json
            

@dataclass
class Form:
    boundary: str
    files: dict[str, list[tempfile._TemporaryFileWrapper]]
    fields: dict[str, list[tempfile._TemporaryFileWrapper]]
class FormParse:
    @staticmethod
    async def parse(boundary_: str, content_iter, length: int) -> 'Form':
        boundary = b'\r\n--' + boundary_.encode("utf-8")
        if length == 0:
            return Form(boundary_, {}, {})
        files: dict[str, list[tempfile._TemporaryFileWrapper]] = {}
        fields: dict[str, list[tempfile._TemporaryFileWrapper]] = {}
        async def read_in_chunks(content_iter):
            yield b'\r\n'
            async for data in content_iter:
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
        async for chunk in read_in_chunks(content_iter):
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
            await asyncio.sleep(0.001)
        process_part(boundary, files, fields, b''.join(buffer), temp_file)
        if temp_file:
            temp_file.seek(0) # type: ignore
        return Form(boundary_, files, fields)


app: Application = Application()

async def handle(data, client: Client):
    try:
        request: Request = Request(data, client)
        await app.handle(request, client)
        await request.skip()
        print(request.get_request_time(), "|", request.method.ljust(6), request.get_status_code(), "|", request.get_ip().ljust(16), "|", request.url, request.get_user_agent())
    except TimeoutError:
        ...
    except:
        traceback.print_exc()