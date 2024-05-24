import asyncio
import base64
from collections import defaultdict
from dataclasses import asdict, dataclass
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
import stat
import struct
import tempfile
import time
import traceback
import zlib
from core.exceptions import (
    WebSocketError,
    ServerWebSocketUnknownDataError,
)
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Callable,
    Coroutine,
    Generator,
    Iterator,
    Optional,
    Union,
    get_args,
)

import aiofiles
from core.utils import (
    CONTENT_ACCEPT,
    WEBSOCKETCONTENT,
    Client,
    calc_bytes,
    content_next,
    parse_obj_as_type,
    parseObject,
)
import filetype
import urllib.parse as urlparse

# from core import timer as Timer
from core.logger import logger
from core.config import Config
from core.utils import Client
from core.const import *
from . import scheduler


@dataclass
class Cookie:
    name: str
    value: str
    domain: Optional[str] = None
    path: Optional[str] = None
    expires: Optional[int] = None
    max_age: Optional[int] = None
    size: Optional[int] = None
    http_only: Optional[bool] = None
    secure: Optional[bool] = None
    same_site: Optional[str] = None
    priority: Optional[str] = None

    def __str__(self) -> str:

        cookie_str = f"{self.name}={self.value}"
        for attr, value in asdict(self).items():
            if attr in ["name", "value"] or value is None:
                continue
            if attr == "http_only" or attr == "secure":
                if value:
                    cookie_str += f"; {attr.capitalize()}"
            else:
                cookie_str += f"; {attr}={urlparse.quote(str(value))}"
        return cookie_str

    @classmethod
    def from_request_string(cls, cookie_str: str) -> list["Cookie"]:
        cookies: list = []
        for cookie in cookie_str.split("; "):
            key, value = None, None
            if "=" in cookie:
                key, value = cookie.split("=", 1)
                cookies.append(Cookie(key, urlparse.unquote(value)))
        return cookies


class Route:
    def __init__(
        self,
        path: str,
        method: Optional[str],
        handler: Callable[..., Coroutine],
        response_configuration: Optional["ResponseConfiguration"] = None,
        **kwargs,
    ) -> None:
        self._path = path if path.startswith("/") else "/" + path
        self._params = path.count("{") == path.count("}") != 0
        self.handler = handler
        self.method = method or "GET"
        if self._params:
            self.param = re.findall(r"{(\w+)}", path)
            self.regexp: re.Pattern = re.compile(
                rf"^{path.replace('{', '(?P<').replace('}', r'>[^/]*)')}$"
            )
        self._response = response_configuration
        self.kwargs = kwargs

    def is_params(self):
        return self._params

    def __str__(self) -> str:
        return 'Route(path="{}", method="{}", handler="{}")'.format(
            self._path, self.method, self.handler
        )

    def __repr__(self) -> str:
        return self.__str__()


class Router:
    def __init__(self, prefix: str = "", *routes: Route) -> None:
        self.prefix = (
            (prefix if prefix.startswith("/") else "/" + prefix) if prefix else ""
        )
        self._routes: dict[str, list[Route]] = {
            method: [] for method in ("GET", "POST", "PUT", "DELETE", "WebSocket")
        }
        self._redirects: dict[str, str] = {}
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
        if not url.startswith(self.prefix) or method not in self._routes:
            return None
        url = url.removeprefix(self.prefix)
        for route in self._routes[method]:
            if route.is_params() and route.regexp.match(url) or route._path == url:
                return route
        return None

    def get_prefix(self) -> str:
        return self.prefix

    def get_redirect(self, url: str) -> Optional[str]:
        if not url.startswith(self.prefix):
            return None
        return self._redirects.get(url.removeprefix(self.prefix), None)

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
        return self.route(path, "GET")

    def post(self, path):
        return self.route(path, "POST")

    def websocket(self, path):
        return self.route(path, "WebSocket")

    def redierct(self, path: str, redirect_to: str):
        self._redirects[path] = redirect_to


class Resource:
    def __init__(self, url: str, path: Path, show_dir: bool = False) -> None:
        if not path.exists():
            raise RuntimeError(f"The path {path} is not dir.")
        self.path = path
        self.dir = str(path.absolute()).replace("\\", "/").removesuffix("/")
        self.url = f"/" + url.lstrip("/")
        self.show_dir = show_dir

    async def __call__(self, request: "Request") -> Any:
        if self.path.is_file():
            return self.dir
        path = self.dir + "/" + request.path.removeprefix(self.url)
        filepath = Path(self.dir + "/" + request.path.removeprefix(self.url))
        if filepath.is_dir():
            if path == "" and not path.endswith("/"):
                return RedirectResponse(request.get_url() + "/")
            if self.show_dir:
                content = """<!DOCTYPE html><html dir="ltr" lang="zh"><head><meta charset="utf-8"><meta name="color-scheme" content="light dark"><meta name="google" value="notranslate"><script>function addRow(e,t,n,a,d,r,l){if("."!=e&&".."!=e){var o=document.location.pathname;"/"!==o.substr(-1)&&(o+="/");var c=document.getElementById("tbody"),i=document.createElement("tr"),s=document.createElement("td"),m=document.createElement("a");m.className=n?"icon dir":"icon file",n?(e+="/",t+="/",a=0,d=""):(m.draggable="true",m.addEventListener("dragstart",onDragStart,!1)),m.innerText=e,m.href=o+t,s.dataset.value=e,s.appendChild(m),i.appendChild(s),i.appendChild(createCell(a,d)),i.appendChild(createCell(r,l)),c.appendChild(i)}}function onDragStart(e){var t=e.srcElement,n="application/octet-stream:"+t.innerText.replace(":","")+":"+t.href;e.dataTransfer.setData("DownloadURL",n),e.dataTransfer.effectAllowed="copy"}function createCell(e,t){var n=document.createElement("td");return n.setAttribute("class","detailsColumn"),n.dataset.value=e,n.innerText=t,n}function start(e){var t=document.getElementById("header");t.innerText=t.innerText.replace("LOCATION",e),document.getElementById("title").innerText=t.innerText}function onHasParentDirectory(){document.getElementById("parentDirLinkBox").style.display="block";var e=document.location.pathname;e.endsWith("/")||(e+="/"),document.getElementById("parentDirLink").href=e+".."}function sortTable(e){var t=document.getElementById("theader"),n=t.cells[e].dataset.order||"1",a=0-(n=parseInt(n,10));t.cells[e].dataset.order=a;var d,r=document.getElementById("tbody"),l=r.rows,o=[];for(d=0;d<l.length;d++)o.push(l[d]);for(o.sort((function(t,d){var r=t.cells[e].dataset.value,l=d.cells[e].dataset.value;return e?(r=parseInt(r,10))>(l=parseInt(l,10))?a:r<l?n:0:r>l?a:r<l?n:0})),d=0;d<o.length;d++)r.appendChild(o[d])}function addHandlers(e,t){e.onclick=e=>sortTable(t),e.onkeydown=e=>{"Enter"!=e.key&&" "!=e.key||(sortTable(t),e.preventDefault())}}function onLoad(){addHandlers(document.getElementById("nameColumnHeader"),0),addHandlers(document.getElementById("sizeColumnHeader"),1),addHandlers(document.getElementById("dateColumnHeader"),2)}window.addEventListener("DOMContentLoaded",onLoad);</script><style>h1{border-bottom: 1px solid #c0c0c0;margin-bottom: 10px;padding-bottom: 10px;white-space:nowrap;}table{border-collapse:collapse;}th{cursor:pointer;}td.detailsColumn{padding-inline-start:2em;text-align:end;white-space:nowrap;}a.icon{padding-inline-start:1.5em;text-decoration:none;user-select:auto;}a.icon:hover{text-decoration:underline;}a.file{background:url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAABnRSTlMAAAAAAABupgeRAAABEElEQVR42nRRx3HDMBC846AHZ7sP54BmWAyrsP588qnwlhqw/k4v5ZwWxM1hzmGRgV1cYqrRarXoH2w2m6qqiqKIR6cPtzc3xMSML2Te7XZZlnW7Pe/91/dX47WRBHuA9oyGmRknzGDjab1ePzw8bLfb6WRalmW4ip9FDVpYSWZgOp12Oh3nXJ7nxoJSGEciteP9y+fH52q1euv38WosqA6T2gGOT44vry7BEQtJkMAMMpa6JagAMcUfWYa4hkkzAc7fFlSjwqCoOUYAF5RjHZPVCFBOtSBGfgUDji3c3jpibeEMQhIMh8NwshqyRsBJgvF4jMs/YlVR5KhgNpuBLzk0OcUiR3CMhcPaOzsZiAAA/AjmaB3WZIkAAAAASUVORK5CYII=") left top no-repeat;}a.dir{background:url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABt0lEQVR42oxStZoWQRCs2cXdHTLcHZ6EjAwnQWIkJyQlRt4Cd3d3d1n5d7q7ju1zv/q+mh6taQsk8fn29kPDRo87SDMQcNAUJgIQkBjdAoRKdXjm2mOH0AqS+PlkP8sfp0h93iu/PDji9s2FzSSJVg5ykZqWgfGRr9rAAAQiDFoB1OfyESZEB7iAI0lHwLREQBcQQKqo8p+gNUCguwCNAAUQAcFOb0NNGjT+BbUC2YsHZpWLhC6/m0chqIoM1LKbQIIBwlTQE1xAo9QDGDPYf6rkTpPc92gCUYVJAZjhyZltJ95f3zuvLYRGWWCUNkDL2333McBh4kaLlxg+aTmyL7c2xTjkN4Bt7oE3DBP/3SRz65R/bkmBRPGzcRNHYuzMjaj+fdnaFoJUEdTSXfaHbe7XNnMPyqryPcmfY+zURaAB7SHk9cXSH4fQ5rojgCAVIuqCNWgRhLYLhJB4k3iZfIPtnQiCpjAzeBIRXMA6emAqoEbQSoDdGxFUrxS1AYcpaNbBgyQBGJEOnYOeENKR/iAd1npusI4C75/c3539+nbUjOgZV5CkAU27df40lH+agUdIuA/EAgDmZnwZlhDc0wAAAABJRU5ErkJggg==") left top no-repeat;}a.up{background:url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACM0lEQVR42myTA+w1RxRHz+zftmrbdlTbtq04qRGrCmvbDWp9tq3a7tPcub8mj9XZ3eHOGQdJAHw77/LbZuvnWy+c/CIAd+91CMf3bo+bgcBiBAGIZKXb19/zodsAkFT+3px+ssYfyHTQW5tr05dCOf3xN49KaVX9+2zy1dX4XMk+5JflN5MBPL30oVsvnvEyp+18Nt3ZAErQMSFOfelCFvw0HcUloDayljZkX+MmamTAMTe+d+ltZ+1wEaRAX/MAnkJdcujzZyErIiVSzCEvIiq4O83AG7LAkwsfIgAnbncag82jfPPdd9RQyhPkpNJvKJWQBKlYFmQA315n4YPNjwMAZYy0TgAweedLmLzTJSTLIxkWDaVCVfAbbiKjytgmm+EGpMBYW0WwwbZ7lL8anox/UxekaOW544HO0ANAshxuORT/RG5YSrjlwZ3lM955tlQqbtVMlWIhjwzkAVFB8Q9EAAA3AFJ+DR3DO/Pnd3NPi7H117rAzWjpEs8vfIqsGZpaweOfEAAFJKuM0v6kf2iC5pZ9+fmLSZfWBVaKfLLNOXj6lYY0V2lfyVCIsVzmcRV9Y0fx02eTaEwhl2PDrXcjFdYRAohQmS8QEFLCLKGYA0AeEakhCCFDXqxsE0AQACgAQp5w96o0lAXuNASeDKWIvADiHwigfBINpWKtAXJvCEKWgSJNbRvxf4SmrnKDpvZavePu1K/zu/due1X/6Nj90MBd/J2Cic7WjBp/jUdIuA8AUtd65M+PzXIAAAAASUVORK5CYII=") left top no-repeat;}html[dir=rtl]a{background-position-x:right;}#parentDirLinkBox{margin-bottom:10px;padding-bottom:10px;}</style><title id="title"></title></head><body><h1 id="header">LOCATION 的索引</h1><div id="parentDirLinkBox" style="display:none"><a id="parentDirLink" class="icon up"><span id="parentDirText">[父目录]</span></a></div><table><thead><tr class="header" id="theader"><th id="nameColumnHeader" tabindex=0 role="button">名称</th><th id="sizeColumnHeader" class="detailsColumn" tabindex=0 role="button">大小</th><th id="dateColumnHeader" class="detailsColumn" tabindex=0 role="button">修改日期</th></tr></thead><tbody id="tbody"></tbody></table></body></html><script>var loadTimeData;class LoadTimeData{constructor(){this.data_=null}set data(value){expect(!this.data_,"Re-setting data.");this.data_=value}valueExists(id){return id in this.data_}getValue(id){expect(this.data_,"No data. Did you remember to include strings.js?");const value=this.data_[id];expect(typeof value!=="undefined","Could not find value for "+id);return value}getString(id){const value=this.getValue(id);expectIsType(id,value,"string");return value}getStringF(id,var_args){const value=this.getString(id);if(!value){return""}const args=Array.prototype.slice.call(arguments);args[0]=value;return this.substituteString.apply(this,args)}substituteString(label,var_args){const varArgs=arguments;return label.replace(/\\$(.|$|\\n)/g,(function(m){expect(m.match(/\\$[$1-9]/),"Unescaped $ found in localized string.");return m==="$$"?"$":varArgs[m[1]]}))}getBoolean(id){const value=this.getValue(id);expectIsType(id,value,"boolean");return value}getInteger(id){const value=this.getValue(id);expectIsType(id,value,"number");expect(value===Math.floor(value),"Number isn't integer: "+value);return value}overrideValues(replacements){expect(typeof replacements==="object","Replacements must be a dictionary object.");for(const key in replacements){this.data_[key]=replacements[key]}}}function expect(condition,message){if(!condition){throw new Error("Unexpected condition on "+document.location.href+": "+message)}}function expectIsType(id,value,type){expect(typeof value===type,"["+value+"] ("+id+") is not a "+type)}expect(!loadTimeData,"should only include this file once");loadTimeData=new LoadTimeData;window.loadTimeData=loadTimeData;console.warn("crbug/1173575, non-JS module files deprecated.");</script><script>loadTimeData.data = {"header":"LOCATION 的索引","headerDateModified":"修改日期","headerName":"名称","headerSize":"大小","language":"zh","parentDirText":"[父目录]","textdirection":"ltr"};</script>"""
                content += f"<script>start(\"{'.' + request.path}\")</script>"
                if request.path.count("/") >= 2:
                    content += f"<script>onHasParentDirectory();</script>"
                dirs = []
                files = []
                for file in os.listdir(filepath):
                    abs_path = os.path.join(filepath, file)
                    if os.path.isdir(abs_path):
                        dirs.append(file)
                    else:
                        files.append(file)
                for dir in dirs:
                    abs_path = os.path.join(filepath, dir)
                    m = os.path.getmtime(abs_path)
                    md = datetime.datetime.fromtimestamp(m)
                    content += f'<script>addRow("{dir}","{dir}", 1, 0, "0", {int(m)}, "{md.year:04d}/{md.month:02d}/{md.day:02d} {md.hour:02d}:{md.minute:02d}:{md.second:02d}")</script>'
                for file in files:
                    abs_path = os.path.join(filepath, file)
                    m = os.path.getmtime(abs_path)
                    md = datetime.datetime.fromtimestamp(m)
                    size = os.path.getsize(abs_path)
                    content += f'<script>addRow("{file}","{file}", 0, {size}, "{calc_bytes(size).removesuffix("iB") + "B"}", {int(m)}, "{md.year:04d}/{md.month:02d}/{md.day:02d} {md.hour:02d}:{md.minute:02d}:{md.second:02d}")</script>'
                return content
            else:
                for redirect in FILE_REDIRECTS:
                    if os.path.exists(os.path.join(filepath, redirect)):
                        return Path(os.path.join(filepath, redirect))
        elif filepath.is_file():
            return filepath
        return Response("Not Found", status_code=404)


class WebSocketOpcode(Enum):
    CONTINUATION = 0
    TEXT = 1
    BINARY = 2
    CLOSE = 8
    PING = 9
    PONG = 10


class WebSocketFrame:
    def __init__(self, opcode: int, data: io.BytesIO) -> None:
        self.opcode = opcode
        self.data = data
        self.close = self.opcode == WebSocketOpcode.CLOSE.value
        if self.close:
            self.status = int.from_bytes(self.data.getbuffer()[:2], byteorder="big")
            self.reason = self.data.getbuffer()[:2]
        self.content = data
        if self.opcode == WebSocketOpcode.TEXT.value:
            try:
                self.content = self.content.getvalue().decode("utf-8")
            except:
                ...
        if isinstance(self.content, io.BytesIO):
            self.content = self.content.getvalue()

    def __str__(self) -> str:
        return "{} {}".format(self.opcode, self.content)

    def __repr__(self) -> str:
        return self.__str__()


class WebSocket:
    def __init__(self, conn: Client) -> None:
        self.conn = conn
        self.keepalive_checked = True
        self.closed = False

    def start(self):
        self.keepalive_thread = asyncio.create_task(self._keepalive())

    async def _get_content(self, data):
        content: io.BytesIO = io.BytesIO()
        if isinstance(data, (Generator, Iterator, AsyncGenerator, AsyncIterator)):
            async for data in self._iter(data):
                content.write(str(content).encode("utf-8"))
        elif isinstance(data, (list, dict, tuple, set)):
            content.write(json.dumps(data).encode("utf-8"))
        elif isinstance(data, str):
            content.write(data.encode("utf-8"))
        elif isinstance(data, (memoryview, bytes)):
            content = io.BytesIO(data)
        elif isinstance(data, io.BytesIO):
            content = data
        else:
            raise ServerWebSocketUnknownDataError("Type: " + str(type(data)))
        return content

    def _get_opcode(self, data):
        if isinstance(
            data,
            (
                Generator,
                Iterator,
                AsyncGenerator,
                AsyncIterator,
                list,
                dict,
                tuple,
                set,
                str,
            ),
        ):
            return WebSocketOpcode.TEXT
        else:
            return WebSocketOpcode.BINARY

    async def _iter(self, content):
        if isinstance(content, (AsyncGenerator, AsyncIterator)):
            async for data in content:
                yield data
        elif isinstance(content, (Generator, Iterator)):
            async for data in content_next(content):
                yield data
        else:
            yield content

    def _build_frame(
        self, content: memoryview, opcode: WebSocketOpcode, status: int = 0
    ):
        data = io.BytesIO()
        close = opcode == WebSocketOpcode.CLOSE
        payload = len(content)
        head1 = 0b10000000 | opcode.value
        head2 = 0
        if not close:
            first = True
            cur = 0
            while cur < payload:
                header = 0b10000000 if payload <= cur + 65535 else 0
                if first:
                    head1 = header | opcode.value
                    first = False
                else:
                    head1 = header | WebSocketOpcode.CONTINUATION.value
                length = min(payload - cur, 65535)
                if length < 126:
                    data.write(struct.pack("!BB", head1, head2 | length))
                elif length < 65536:
                    data.write(struct.pack("!BBH", head1, head2 | 126, length))
                else:
                    data.write(struct.pack("!BBQ", head1, head2 | 127, length))
                data.write(content[cur : length + cur])
                cur += length
        else:
            if payload > 123:
                content = content[:123]
                payload = len(content)
            data.write(struct.pack("!BB", 0b10000000 | opcode.value, 0 | payload + 2))
            data.write(struct.pack("!H", status))
            data.write(content)
        return data

    async def send(
        self, data: WEBSOCKETCONTENT, opcode: Optional[WebSocketOpcode] = None
    ):
        if self.is_closed():
            return
        self.conn.write(
            self._build_frame(
                (await self._get_content(data)).getbuffer(),
                opcode or self._get_opcode(data),
                0,
            ).getbuffer()
        )
        await self.conn.drain()

    async def close(self, data: WEBSOCKETCONTENT = b"", status: int = 1000):
        if self.is_closed():
            return
        self.conn.write(
            self._build_frame(
                (await self._get_content(data)).getbuffer(),
                WebSocketOpcode.CLOSE,
                status,
            ).getbuffer()
        )
        await self.conn.drain()
        self.keepalive_thread.cancel()
        self.closed = True
        await self.conn.writer.wait_closed()

    async def _read_frame(self):
        if self.is_closed():
            return None
        try:
            head1, head2 = struct.unpack("!BB", await self.conn.readexactly(2))
            fin = bool(head1 & 0b10000000)
            mask = bool((head1 & 0x80) >> 7)
            opcode = head1 & 0b00001111
            length = head2 & 0b01111111
            mask_bits = b""
            if length == 126:
                (length,) = struct.unpack("!H", await self.conn.readexactly(2))
            elif length == 127:
                (length,) = struct.unpack("!Q", await self.conn.readexactly(2))
            if mask:
                mask_bits = await self.conn.readexactly(4)
            data = await self.conn.readexactly(length)
            content = io.BytesIO()
            if (mask and mask_bits is None) or (
                mask and mask_bits and len(mask_bits) != 4
            ):
                raise ValueError("mask must contain 4 bytes")
            if mask:
                content.write(
                    b"".join(
                        (
                            (data[i] ^ mask_bits[i % 4]).to_bytes()
                            for i in range(len(data))
                        )
                    )
                )
            if opcode == 8:
                self.conn.close()
                return WebSocketFrame(opcode, content)
            if not fin:
                frame = await self._read_frame()
                if (
                    not frame
                    or frame.opcode != WebSocketOpcode.CONTINUATION.value
                    and len(content.getbuffer()) + len(frame.data.getbuffer()) != length
                ):
                    raise ValueError(
                        "opcode doesn't match {} {}".format(opcode, length)
                    )
                content.write(frame.data.getbuffer())
            return WebSocketFrame(opcode, content)
        except:
            return None

    def is_closed(self):
        return self.conn.is_closed() or self.closed

    async def _keepalive(self):
        while self.keepalive_checked and not self.is_closed():
            self.keepalive_checked = False
            await self.send(str(time.time()), WebSocketOpcode.PING)
            await asyncio.sleep(10)
        if not self.is_closed():
            await self.close()

    async def _read(self):
        frame = await self._read_frame()
        if not frame:
            await self.close()
            raise WebSocketError("No Frame")
        if frame.opcode == WebSocketOpcode.CLOSE:
            await self.close()
            raise WebSocketError("Client Closed")
        if (
            frame.opcode == WebSocketOpcode.PING.value
            or frame.opcode == WebSocketOpcode.PONG.value
        ):
            self.keepalive_checked = True
            return await self._read()
        return frame

    async def read(self):
        return (await self._read()).content

    async def __aiter__(self):
        try:
            while (data := await self.read()) and not self.is_closed():
                yield data
        except:
            ...


class Application:
    def __init__(self) -> None:
        self._routes: list[Router] = [Router()]
        self._resources: list[Resource] = []
        self._ws: dict[str, list[WebSocket]] = {}

    def route(self, path: str, method, **kwargs):
        def decorator(f):
            self._add_route(Route(path, method, f, **kwargs))
            return f

        return decorator

    def _add_route(self, route: Route):
        self._routes[0].add(route)

    def get(self, path, **kwargs):
        return self.route(path, "GET", kwargs=kwargs)

    def post(self, path, **kwargs):
        return self.route(path, "POST", kwargs=kwargs)

    def websocket(self, path, **kwargs):
        return self.route(path, "WebSocket", kwargs=kwargs)

    def redirect(self, path: str, redirect_to: str):
        return self._routes[0].redierct(path, redirect_to)

    async def handle(self, request: "Request"):
        url = request.get_url()
        redirect = None
        for route in self._routes:
            redirect = route.get_redirect(url)
            if redirect:
                break
        if redirect:
            yield RedirectResponse(redirect)
            return
        result = None
        cur_route = None
        response_configuration = None
        method = await request.get_method()
        for route in self._routes:
            cur_route = route.get_route(method, url)
            if cur_route:
                response_configuration = cur_route._response
                prefix = route.get_prefix()
                break
        if cur_route is not None:
            handler = cur_route.handler
            url_params: dict[str, Any] = {}
            if cur_route.is_params():
                r = cur_route.regexp.match(request.get_url().removeprefix(prefix))
                if r:
                    url_params.update({name: r.group(name) for name in cur_route.param})
            annotations = inspect.get_annotations(handler)
            default_params: dict[str, Any] = {
                name.lower(): value.default
                for name, value in inspect.signature(handler).parameters.items()
                if (not isinstance(value, inspect._empty))
                and (value.default != inspect._empty)
            }
            params = {}
            sets = []
            is_json = await request.is_json()
            json = await request.json() or {} if is_json else {}
            ws = WebSocket(request.client)
            response_configuration = None
            for include_name, include_type in annotations.items():
                if include_type == Request:
                    params[include_name] = request
                    sets.append(include_name)
                elif include_type == Form and request.is_form():
                    params[include_name] = request.form()
                    sets.append(include_name)
                elif include_type == WebSocket and method == "WebSocket":
                    params[include_name] = ws
                    sets.append(include_name)
                elif include_type == ResponseConfiguration:
                    params[include_name] = (
                        response_configuration := ResponseConfiguration()
                    )
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
                    elif (
                        hasattr(include_type, "__origin__")
                        and include_type.__origin__ is Union
                        and type(None) in get_args(include_type)
                    ):
                        params[include_name] = None
                    try:
                        params[include_name] = parse_obj_as_type(
                            params[include_name], include_type
                        )
                        sets.append(include_name)
                    except:
                        traceback.print_exc()
                        return
            if method == "WebSocket":
                yield Response(
                    headers=Header(
                        {
                            "Upgrade": "WebSocket",
                            "Connection": "Upgrade",
                            "Sec-WebSocket-Accept": base64.b64encode(
                                hashlib.sha1(
                                    (
                                        await request.get_headers(
                                            "Sec-WebSocket-Key", ""
                                        )
                                    ).encode("utf-8")
                                    + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
                                ).digest()
                            ).decode("utf-8"),
                        }
                    ),
                    status_code=101,
                    response_configuration=response_configuration
                )
                ws.start()
                if request.get_url() not in self._ws:
                    self._ws[request.get_url()] = []
                self._ws[request.get_url()].append(ws)
            try:
                if inspect.iscoroutinefunction(handler):
                    result = await handler(**params)
                else:
                    result = handler(**params)
            except:
                traceback.print_exc()
            if method == "WebSocket":
                self._ws[request.get_url()].remove(ws)
                if not request.client.is_closed():
                    await ws.close("Server Closed.", 1001)
        else:
            for resource in self._resources:
                if request.url.startswith(resource.url):
                    result = await resource(request)
                    break
        if result is None and cur_route is None:
            result = (
                ErrorResonse.not_found(request)
                if method != "WebSocket"
                else ErrorResonse.bad_request(request)
            )
        yield Response(
            content=result or "",
            headers=Header({"Server": Config.get("web.server_name")}),
            response_configuration=response_configuration,
        )

    def mount(self, router: Router):
        self._routes.append(router)
        logger.tinfo("web.info.serving_router", router=router.prefix)

    def mount_resource(self, resource: Resource):
        self._resources.append(resource)
        self._resources.sort(key=lambda x: len(x.url), reverse=True)

    def get_websockets(self, path) -> list[WebSocket]:
        return self._ws.get(path, [])


class Header:
    def __init__(self, header: dict[str, Any] | bytes | str | None = None) -> None:
        self._headers = {}
        if isinstance(header, Header):
            self._headers = header._headers
        elif isinstance(header, bytes):
            self._headers.update(
                {
                    v[0]: v[1]
                    for v in (
                        v.split(": ", 1)
                        for v in header.decode("utf-8").split("\r\n")
                        if v.strip()
                    )
                    if len(v) == 2
                }
            )
        elif isinstance(header, str):
            self._headers.update(
                {
                    v[0]: v[1]
                    for v in (v.split(": ") for v in header.split("\r\n") if v.strip())
                    if len(v) == 2
                }
            )
        elif isinstance(header, dict):
            self._headers.update(header)

    def get(self, key: str, def_=None) -> Any:
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
            self.update(value._headers)
        if not isinstance(value, dict):
            return
        for k, v in value.items():
            self.set(k, v)

    def __str__(self) -> str:
        return "\r\n".join(("{}: {}".format(k, v) for k, v in self._headers.items()))

    def __len__(self) -> int:
        return self._headers.keys().__len__()


@dataclass
class ResponseConfiguration:
    length: Optional[int] = None
    access_log: bool = True


class Response:
    def __init__(
        self,
        content: CONTENT_ACCEPT = None,
        headers: Header | dict[str, Any] = {},
        cookies: list[Cookie] = [],
        content_type: Optional[str] = None,
        compress=None,
        status_code: int = 200,
        response_configuration: Optional[ResponseConfiguration] = None,
        **kwargs,
    ) -> None:
        self.status_code = status_code
        self.content: CONTENT_ACCEPT = content
        self._headers = Header(headers)
        self._cookies = cookies
        self.content_type = content_type
        self._compress = compress
        self._response_configuration = response_configuration
        self._kwargs = kwargs

    def set_headers(self, header: Header | dict[str, Any]):
        self._headers.update(header)
        return self

    def set_cookies(self, cookies: tuple[Cookie, ...]):
        for cookie in cookies:
            self._cookies.append(cookie)
        return self

    def _get_content_type(self, content):
        if isinstance(content, (AsyncGenerator, Iterator, AsyncIterator, Generator)):
            return "application/octet-stream"
        if isinstance(content, str):
            return "text/plain; charset=utf-8"
        content = (
            self.content_type
            or filetype.guess_mime(content)
            or (
                guess_type(content)[0]
                if isinstance(content, Path) and content.exists() and content.is_file()
                else "text/plain"
            )
            or "text/plain"
        )
        content = content.lower()
        if content in ("text/plain", "application/javascript", "text/html"):
            content += f"; charset=utf-8"
        return content

    async def _iter(self):
        if isinstance(self.content, (str, int, float)):
            yield str(self.content).encode("utf-8")
        elif isinstance(self.content, (dict, list, tuple, bool)):
            self.content_type = "application/json"
            yield json.dumps(parseObject(self.content)).encode("utf-8")
        elif isinstance(self.content, (Iterator, Generator)):
            async for data in content_next(self.content):
                yield data
        elif isinstance(self.content, (AsyncIterator, AsyncGenerator)):
            async for data in self.content:
                yield data
        else:
            yield b""

    async def raw(self):
        if isinstance(self.content, Coroutine):
            self.content = await self.content
        if isinstance(self.content, Response):
            self.status_code = self.content.status_code
            self.content_type = self.content.content_type
            self._headers = self.content._headers
            self._cookies = self.content._cookies
            self._kwargs = self.content._kwargs
            self._response_configuration = self.content._response_configuration
            self.content = self.content.content
        if isinstance(self.content, (Coroutine, Response)):
            await self.raw()

    async def __call__(
        self,
        request: "Request",
        client: Client,
        response_configuration: Optional[ResponseConfiguration] = None,
    ) -> Any:
        content, length = io.BytesIO(), 0
        await self.raw()
        if isinstance(self.content, Path):
            if self.content.exists() and self.content.is_file():
                content = self.content
            else:
                content = io.BytesIO(b"Not Found")
        elif isinstance(self.content, (memoryview, bytearray, bytes)):
            content = io.BytesIO(self.content)
            self.content_type = "bytes"
        elif isinstance(self.content, io.BytesIO):
            content = self.content
        elif response_configuration is None or response_configuration.length is None:
            async for data in self._iter():
                content.write(data)
        else:
            content = self.content
        if isinstance(content, Path):
            self.content_type = self.content_type or self._get_content_type(content)
            length = content.stat().st_size
            if length <= RESPONSE_COMPRESSION_IGNORE_SIZE_THRESHOLD:
                async with aiofiles.open(content, "rb") as r:
                    content = io.BytesIO(await r.read())
        elif isinstance(content, io.BytesIO):
            length = len(content.getbuffer())
        start_bytes, end_bytes = 0, 0
        range_str = await request.get_headers("range", "")
        range_match = re.search(r"bytes=(\d+)-(\d+)", range_str, re.S) or re.search(
            r"bytes=(\d+)-", range_str, re.S
        )
        end_bytes = length - 1
        if range_match and self.status_code == 200:
            start_bytes = int(range_match.group(1)) if range_match else 0
            if range_match.lastindex == 2:
                end_bytes = int(range_match.group(2))
            length = (
                length - start_bytes
                if isinstance(self.content, Path)
                and self.content.is_file()
                and stat.S_ISREG(self.content.stat().st_mode)
                else length
            )
            self.set_headers(
                {
                    "Accept-Ranges": "bytes",
                    "Content-Range": f"bytes {start_bytes}-{end_bytes}/{length}",
                }
            )
            self.status_code = 206 if start_bytes > 0 else 200
            length = length - start_bytes
        if isinstance(content, io.BytesIO) and len(content.getbuffer()) != 0:
            self.content_type = self.content_type or self._get_content_type(content)
            compression: Compressor = compressor(
                await request.get_headers("Accept-Encoding", ""),
                content.getbuffer()[start_bytes : end_bytes + 1],
            )
            if compression.type is None:
                content = compression.data
            content = compression
        self.set_headers(
            {
                **RESPONSE_HEADERS,
                "Date": datetime.datetime.fromtimestamp(time.time()).strftime(
                    RESPONSE_DATE
                ),
                "Content-Length": length,
                "Connection": (
                    "Upgrade"
                    if self.status_code == 101
                    else await request.get_headers("Connection") or "Closed"
                ),
                "Content-Type": self.content_type or self._get_content_type(content),
            }
        )
        if isinstance(content, Compressor):
            self.set_headers(
                {
                    "Content-Encoding": compression.type,
                    "Content-Length": len(compression.data),
                }
            )
        headers, cookie = "", ""
        if self._headers:
            headers = str(self._headers) + "\r\n"
        cookies = [
            f"Set-Cookie: {cookie}"
            for cookie in self._cookies
            if cookie.name is not None
        ]
        if cookies:
            cookie = "\r\n".join(cookies) + "\r\n"
        request._end_request_time(self.status_code)
        header = f"{request.protocol} {self.status_code} {STATUS_CODES[self.status_code] if self.status_code in STATUS_CODES else STATUS_CODES[self.status_code // 100 * 100]}\r\n{headers}{cookie}\r\n".encode(
            "utf-8"
        )
        client.write(header)
        if length != 0:
            if isinstance(content, Compressor):
                client.write(content.data)
                await client.drain()
            elif isinstance(content, io.BytesIO):
                client.write(content.getbuffer()[start_bytes : end_bytes + 1])
                await client.drain()
            elif isinstance(content, Path):
                with open(content, "rb") as r:
                    await asyncio.get_event_loop().sendfile(
                        client.writer.transport, r, start_bytes, length
                    )
            else:
                cur_length: int = 0
                bound: bool = False
                async for data in self._iter():
                    cur_length = len(data)
                    if cur_length >= length:
                        data = data[: cur_length - length]
                        bound = True
                    client.write(data)
                    await client.drain()
                    if bound:
                        break
        if (self._headers.get("Connection") or "keep-alive").lower() == "closed":
            client.close()


class TemporarilyRedirectResponse(Response):
    def __init__(
        self, location: str, headers: Header | dict[str, Any] | None = None, response_configuration: Optional[ResponseConfiguration] = None
    ) -> None:
        header = Header()
        header.update(headers)
        header.update({"Location": location})
        super().__init__(headers=header, status_code=307, response_configuration=response_configuration)


class RedirectResponse(Response):
    def __init__(
        self, location: str, headers: Header | dict[str, Any] | None = None, response_configuration: Optional[ResponseConfiguration] = None
    ) -> None:
        header = Header()
        header.update(headers)
        header.update({"Location": location})
        super().__init__(headers=header, status_code=302, response_configuration=response_configuration)


class Request:
    def __init__(self, data: bytes, client: Client):
        self._start = time.time_ns()
        self._info, self._body = data.split(b"\r\n", 1)
        self._end = None
        self._status_code = None
        self._ip = client.get_ip()
        self._user_agent = None
        self.client = client
        self.method, self.url, self.protocol = (
            self._info.decode("utf-8").strip().split(" ")
        )
        self.path = urlparse.unquote((url := urlparse.urlparse(self.url)).path).replace(
            "//", "/"
        )
        self.params = {k: v[-1] for k, v in urlparse.parse_qs(url.query).items()}
        self.parameters: dict[str, str] = {}
        self._headers = {}
        self._cookies: Optional[dict[str, Cookie]] = None
        self._read_content = False
        self._length = 0
        self._read_length = 0
        self._check_websocket = False
        self._json = None
        self._form = None
        self._xff = False

    def is_ssl(self):
        return self.client.is_ssl

    def get_url(self):
        return self.path

    def get_url_params(self):
        return self.params

    def get_ip(self):
        return self._ip

    def get_user_agent(self):
        return self._user_agent or ""

    async def get_method(self):
        if (
            not self._check_websocket
            and self.method == "GET"
            and (await self.get_headers("Connection") or "Closed") == "Upgrade"
        ):
            method = await self.get_headers("Upgrade") or ""
            if method.lower() == "websocket":
                self.method = "WebSocket"
        return self.method

    async def get_headers(self, key: str, def_=None):
        if not self._headers:
            if b"\r\n\r\n" not in self._body:
                self._body += await self.client.readuntil(b"\r\n\r\n")
            data, self._body = self._body.split(b"\r\n\r\n", 1)
            self._headers = Header(data)
            self._user_agent = self._headers.get("user-agent")
            if not self._xff and X_FORWARDED_FOR != 0:
                self._xff = True
                self._ip = (
                    get_xff(
                        await self.get_headers("X-Forwarded-For", ""), X_FORWARDED_FOR
                    )
                    or self._ip
                )
        return self._headers.get(key.lower(), def_)

    async def get_cookies(self):
        if not self._cookies:
            self._cookies = {
                cookie.name: cookie
                for cookie in Cookie.from_request_string(
                    await self.get_headers("cookie", "")
                )
            }
        return self._cookies

    async def length(self):
        return int(await self.get_headers("content-length", "0") or "0")

    async def content_iter(self, buffer: int = IO_BUFFER):
        if self._read_content:
            return
        self._length = int(await self.get_headers("content-length", "0") or "0")
        self._read_content = True
        self._read_length += len(self._body)
        yield self._body
        while (
            data := await self.client.read(
                min(buffer, self._length - self._read_length)
            )
        ) and self._read_length < self._length:
            self._read_length += len(data)
            yield data

    async def read_all(self) -> bytes:
        buf = io.BytesIO()
        async for data in self.content_iter():
            buf.write(data)
        return buf.getvalue()

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
        units = REQUEST_TIME_UNITS[0]
        for unit in REQUEST_TIME_UNITS:
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
        if (
            self.method != "GET"
            or not (content_type).startswith("multipart/form-data")
            or self._form
        ):
            return self._form
        boundary = content_type.split("; boundary=")[1]
        self._form = await FormParse.parse(
            boundary, self.content_iter, await self.length()
        )
        return self._form

    async def is_json(self):
        content_type: str = await self.get_headers("Content-Type") or ""
        return content_type.startswith("application/json") or content_type.startswith(
            "application/x-www-form-urlencoded"
        )

    async def json(self):
        content_type: str = await self.get_headers("Content-Type") or ""
        if (
            not (
                content_type.startswith("application/json")
                or content_type.startswith("application/x-www-form-urlencoded")
            )
            or self._json
        ):
            return self._json
        buf = io.BytesIO()
        async for data in self.content_iter():
            buf.write(data)
        if content_type.startswith("application/json"):
            try:
                self._json = json.load(buf)
            except:
                self._json = None
        elif content_type.startswith("application/x-www-form-urlencoded"):
            self._json = {
                k.decode("utf-8"): v[-1].decode("utf-8")
                for k, v in urlparse.parse_qs(buf.getvalue()).items()
            }
        return self._json


class ErrorResonse:
    @staticmethod
    async def not_found(request: Request):
        if "text/html" in (
            await request.get_headers(
                "Accept",
            )
            or ""
        ):
            return Response("404 Not Found", status_code=404, content_type="text/html")
        return Response("Not Found", status_code=404)

    @staticmethod
    async def bad_request(request: Request):
        if "text/html" in (
            await request.get_headers(
                "Accept",
            )
            or ""
        ):
            return Response(
                "400 Bad Request", status_code=400, content_type="text/html"
            )
        return Response("Bad Request", status_code=400)

    @staticmethod
    async def error(request: Request):
        if "text/html" in (
            await request.get_headers(
                "Accept",
            )
            or ""
        ):
            return Response(
                "502 Internet Error", status_code=502, content_type="text/html"
            )
        return Response("Internet Error", status_code=502)


@dataclass
class Form:
    boundary: str
    files: dict[str, list[tempfile._TemporaryFileWrapper]]
    fields: dict[str, list[tempfile._TemporaryFileWrapper]]


class FormParse:
    @staticmethod
    async def parse(boundary_: str, content_iter, length: int) -> "Form":
        boundary = b"\r\n--" + boundary_.encode("utf-8")
        if length == 0:
            return Form(boundary_, {}, {})
        files: dict[str, list[tempfile._TemporaryFileWrapper]] = {}
        fields: dict[str, list[tempfile._TemporaryFileWrapper]] = {}

        async def read_in_chunks(content_iter):
            yield b"\r\n"
            async for data in content_iter:
                yield data

        def process_part(
            boundary: bytes,
            files: dict[str, list[tempfile._TemporaryFileWrapper]],
            fields: dict[str, list[tempfile._TemporaryFileWrapper]],
            part: bytes,
            temp_file,
        ):
            if b"\r\n\r\n" not in part:
                if temp_file:
                    temp_file.write(part.rstrip(boundary))
                return
            headers, body = part.split(b"\r\n\r\n", 1)
            headers = {
                key: value
                for key, value in (
                    (
                        urlparse.unquote(a.groupdict()["key"]),
                        urlparse.unquote(a.groupdict()["value"]),
                    )
                    for a in re.finditer(
                        r'(?P<key>\w+)="(?P<value>[^"\\]*(\\.[^"\\]*)*)"',
                        headers.decode("utf-8"),
                    )
                )
            }
            temp_file.write(body)
            if "filename" in headers:
                if headers["filename"] not in files:
                    files[headers["filename"]] = []
                files[headers["filename"]].append(temp_file)
            if "name" in headers:
                if headers["name"] not in fields:
                    fields[headers["name"]] = []
                fields[headers["name"]].append(temp_file)

        buffer = []
        temp_file = None
        async for chunk in read_in_chunks(content_iter):
            buffer.append(chunk)
            while boundary in b"".join(buffer):
                t = [t for t in (b"".join(buffer)).split(boundary) if t]
                if temp_file is not None:
                    process_part(boundary, files, fields, t[0], temp_file)
                    temp_file.seek(0)
                    temp_file = tempfile.TemporaryFile()
                    t = t[1:]
                part, tm = t[0], b"" if len(t) == 1 else boundary.join(t[1:])
                buffer = [tm]
                temp_file = tempfile.TemporaryFile()
                process_part(boundary, files, fields, part, temp_file)
            while len(buffer) >= 2 and temp_file is not None:
                temp_file.write(b"".join(buffer[:-1]))
                buffer = buffer[-1:]
            await asyncio.sleep(0.001)
        process_part(boundary, files, fields, b"".join(buffer), temp_file)
        if temp_file:
            temp_file.seek(0)
        return Form(boundary_, files, fields)


class Statistics:
    def __init__(self) -> None:
        self.qps: defaultdict[int, int] = defaultdict(int)
        scheduler.repeat(self._clear, delay=1, interval=1)

    def _clear(self):
        t = self.get_time()
        pops = []
        for k in self.qps.keys():
            if t - k > 86400:
                pops.append(k)
        for pop in pops:
            self.qps.pop(pop)

    def add_qps(self):
        t = self.get_time()
        self.qps[t] += 1

    def get_time(self):
        return int(time.time())

    def get_cur_qps(self):
        return self.qps.get(self.get_time(), 0)

    def get_in_time_qps(self, t: float):
        c = self.get_time()
        return {k: v for k, v in self.qps.copy().items() if k - t <= c}

    def get_all_qps(self):
        return self.qps.copy()


@dataclass
class Compressor:
    type: Optional[str]
    data: io.BytesIO


def get_xff(x_forwarded_for: str, index: int = 1):
    index -= 1
    ip_addresses = x_forwarded_for.split(",")
    if not ip_addresses:
        return None
    return ip_addresses[min(len(ip_addresses) - 1, index)].strip()


def compressor(header: str, data: io.BytesIO | bytes | memoryview) -> Compressor:
    if isinstance(data, io.BytesIO):
        data = data.getbuffer()
    for key, compressor in COMPRESSOR.items():
        if key in header:
            return Compressor(key, compressor(data))
    return Compressor(None, data)


statistics: Statistics = Statistics()
app: Application = Application()


async def handle(data, client: Client):
    try:
        request: Request = Request(data, client)
        statistics.add_qps()
        if FORCE_SSL and not client.is_ssl:
            await TemporarilyRedirectResponse(
                "https://" + await request.get_headers("Host") + request.url
            )(request, client)
            await request.skip()
            request.client.set_log_network(None)
            return
        log = False
        async for resp in app.handle(request):
            await resp(request, client)
            if not log:
                log = True
                if resp._response_configuration is None or resp._response_configuration.access_log:
                    logger.info(
                        request.get_request_time(),
                        "|",
                        (await request.get_method()).ljust(9),
                        request.get_status_code(),
                        "|",
                        request.get_ip().ljust(16),
                        "|",
                        request.url,
                        request.get_user_agent(),
                    )
        await request.skip()
        request.client.set_log_network(None)
    except TimeoutError:
        ...
    except:
        traceback.print_exc()


@app.get("/favicon.ico")
async def _():
    return zlib.decompress(
        b'x\x9cc``d`b\x10\x10`\x00\xd2\n\x0c\x19,\x0c\x0cj\x0c\x0c\x0c\n\n\x10\xbe\x86 \x03C\x1fPL\x03(&\x00\x12g\x80\x88\x83\x01\x0b\x03\x06\x90\xe1\xfd\xfd\x7f\x14\x0f\x1e\x0c\x8c\x12\xac\x98^\xfaG:F\x0f/r\xc3\x9f\\\xfd\x03\xe0_\x8a\x80\x06\xb4\x8cq@.g\x04F\xcb\x99Q<\x8aG\xf1(\x1e*X\x9a\xe7\x0bI\x98\xdav32\xf2\x01\xeb"v\xa20H-5\xdd\x002\x0bb6\xf6\xb6\x13&f\x1fv\xf6\x0fd\xf8\x0ft\xfa\x1b\xc5\xa3x\xa4cB\xf9\x8b\x9e\xe5?z\xf9BH\x9e\x1a\xf6\xa3\x96\xbf\xec\x18\xf6\xe3\x93\x1f\x0e\xf6\x0fd\xf8\x0ft\xfa\x1b\xc5\xb4\xc7\x94\x8e3\x0cu\x00\x00-\xd7@W'
    )
