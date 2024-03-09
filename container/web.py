import asyncio
import base64
from dataclasses import dataclass
import datetime
import inspect
import io
import json
from mimetypes import guess_type
import os
from pathlib import Path
import re
import tempfile
import time
import traceback
from typing import Any, AsyncGenerator, AsyncIterator, Callable, Coroutine, Generator, Iterator, Optional, Union, get_args

import aiofiles
from utils import CONTENT_ACCEPT, Client, calc_bytes, content_next, parse_obj_as_type
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
    def __init__(self, url: str, path: Path, show_dir: bool = False) -> None:
        if not path.exists():
            raise RuntimeError(f"The path {path} is not dir.")
        self.path = path
        self.dir = str(path.absolute()).replace("\\", "/").removesuffix("/")
        self.url = f"/" + url.lstrip("/")
        self.show_dir = show_dir
    async def __call__(self, request: 'Request') -> Any:
        if self.path.is_file():
            return self.dir
        path = (self.dir + request.path.removeprefix(self.url))
        filepath = Path(self.dir + request.path.removeprefix(self.url))
        if filepath.is_dir() and self.show_dir:
            if not path.endswith("/"):
                return RedirectResponse(request.get_url() + "/")
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
        elif filepath.is_file():
            return filepath
        return Response("Not Found", status_code=404)

class Application:
    def __init__(self) -> None:
        self._routes: list[Router] = [Router()]
        self._resources: list[Resource] = []
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
    async def handle(self, request: 'Request'):
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
            url_params: dict[str, Any] = {}
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
        else:
            for resource in self._resources:
                if request.url.startswith(resource.url):
                    result = await resource(request)
                    break
        if result == None:
            accept = await request.get_headers("Accept", ) or ""
            if "text/html" in accept:
                result = ClientErrorResonse.not_found(request)
        yield Response(content=result or '', headers=Header({ # type: ignore
            "Server": "TTB-Network"
        }))
    def mount(self, router: Router):
        self._routes.append(router)
        print(f"Serve router at: {router.prefix}")
    def mount_resource(self, resource: Resource):
        self._resources.append(resource)

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
    def _get_content_type(self, content):
        if isinstance(content, (AsyncGenerator, Iterator, AsyncIterator, Generator)):
            return "bytes"
        content = self.content_type or filetype.guess_mime(content) or (guess_type(content)[0] if isinstance(content, Path) and content.exists() and content.is_file() else "text/plain") or "text/plain"
        content = content.lower()
        if content in ("text/plain", "application/javascript", "text/html"):
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
            self.status_code = self.content.status_code
            self.content_type = self.content.content_type
            self._headers = self.content._headers
            self.content = self.content.content
        if isinstance(self.content, Path):
            if self.content.exists() and self.content.is_file(): content = self.content
            else: content = io.BytesIO(b"Not Found")
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
                "Content-Type": self.content_type or self._get_content_type(content),
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

class RedirectResponse(Response):
    def __init__(self, location: str) -> None:
        super().__init__(headers=Header(
            {
                "Location": location
            }
        ), status_code=301)

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

class ClientErrorResonse:
    @staticmethod
    def not_found(request: Request):      
        return Response("404 Not Found", status_code=404, content_type="text/html")

class ApplicationErrorResonse:
    @staticmethod
    def not_found(request: Request):      
        return Response("Not Found", status_code=404)
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
        async for resp in app.handle(request):
            await resp(request, client)
        await request.skip()
        print(request.get_request_time(), "|", request.method.ljust(6), request.get_status_code(), "|", request.get_ip().ljust(16), "|", request.url, request.get_user_agent())
    except TimeoutError:
        ...
    except:
        traceback.print_exc()


import asyncio
from pathlib import Path
import ssl
import traceback
from typing import Optional
import config
from utils import Client
import web
server: Optional[asyncio.Server] = None
cert = None
cur_ssl = False
def get_ssl():
    global cur_ssl
    return cur_ssl

def load_cert():
    global cert, cur_ssl
    if Path(".ssl/cert.pem").exists() and Path(".ssl/key.pem").exists():
        cert = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        cert.check_hostname = False
        cert.load_cert_chain(Path(".ssl/cert.pem"), Path(".ssl/key.pem"))
        if server:
            server.close()
        cur_ssl = True
    else:
        cur_ssl = False

async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    client = Client(reader, writer)
    timeout = config.TIMEOUT
    try:
        while (type := await client.readuntil(b"\r\n", timeout=timeout)):
            if client.invaild_ip():
                break
            if b'HTTP/1.1' in type:
                await web.handle(type, client)
            timeout = 10
    except (TimeoutError, asyncio.exceptions.IncompleteReadError, ConnectionResetError) as e:
        ...
    except:
        traceback.print_exc()
async def main():
    global cert, server
    print(f"Loading...")
    load_cert()
    import cluster
    await cluster.init()
    while 1:
        try:
            server = await asyncio.start_server(_handle, host='0.0.0.0', port=config.PORT, ssl=cert)
            print(f"Server listen on {config.PORT}{' with ssl' if cert else ''}!")
            await server.serve_forever()
        except:
            if server:
                server.close()
            traceback.print_exc()

@app.get("/favicon.ico")
async def _():
    return base64.b64decode("AAABAAIAEBAAAAEAIABoBAAAJgAAACAgAAABACAAKBEAAI4EAAAoAAAAEAAAACAAAAABACAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAHA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/wAAAP8AAAD/HA37/xwN+/8AAAD/AAAA/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8AAAD/AAAA/xwN+/8cDfv/AAAA/wAAAP8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAoAAAAIAAAAEAAAAABACAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAHA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/Gwz0/xsM9P8bDPT/Gwz0/xsM9P8bDPT/Gwz0/xsM9P8bDPT/Gwz0/xsM9P8bDPT/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xsM9P8BAQ7/AAAH/wAAB/8AAAf/AAAH/wAAB/8AAAf/AAAH/wAAB/8AAAf/AAAH/wEBDv8bDPT/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/Gwz0/wAAB/8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAH/xsM9P8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8bDPT/AAAH/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAf/Gwz0/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xsM9P8BAQ7/AAAH/wAAB/8AAAf/AAAH/wAAB/8AAAf/AAAH/wAAB/8AAAf/AAAH/wEBDv8bDPT/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xsM9P8bDPT/Gwz0/xsM9P8bDPT/Gwz0/xsM9P8bDPT/Gwz0/xsM9P8bDPT/Gwz0/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/Gwz0/xsM9P8bDPT/Gwz0/xwN+/8cDfv/HA37/xwN+/8bDPT/Gwz0/xsM9P8bDPT/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xsM9P8BAQ7/AAAH/wAAB/8BAQ7/Gwz0/xwN+/8cDfv/Gwz0/wEBDv8AAAf/AAAH/wEBDv8bDPT/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/Gwz0/wAAB/8AAAD/AAAA/wAAB/8bDPT/HA37/xwN+/8bDPT/AAAH/wAAAP8AAAD/AAAH/xsM9P8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8bDPT/AAAH/wAAAP8AAAD/AAAH/xsM9P8cDfv/HA37/xsM9P8AAAf/AAAA/wAAAP8AAAf/Gwz0/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xsM9P8BAQ7/AAAH/wAAB/8BAQ7/Gwz0/xwN+/8cDfv/Gwz0/wEBDv8AAAf/AAAH/wEBDv8bDPT/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xsM9P8bDPT/Gwz0/xsM9P8cDfv/HA37/xwN+/8cDfv/Gwz0/xsM9P8bDPT/Gwz0/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/xwN+/8cDfv/HA37/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

def init():
    asyncio.run(main())