import asyncio
from collections import deque
from dataclasses import dataclass
import io
import os
from pathlib import Path
import time
from typing import Any, Optional
from aiohttp import web
from aiohttp.web_urldispatcher import SystemRoute

from core import scheduler

from . import units
from . import config
from .logger import logger
import ssl

qps: int = 0
xff: int = config.const.xff

class SNIHelper:
    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)
        self.seek(43)
        length = self.buffer.read(1)[0]
        self.seek(length)
        length = int.from_bytes(self.buffer.read(2), 'big')
        self.seek(length)
        length = self.buffer.read(1)[0]
        self.seek(length)
        extensions_length = int.from_bytes(self.buffer.read(2), 'big')
        current_extension_cur = 0
        extensions = []
        self.sni = None
        while current_extension_cur < extensions_length:
            extension_type = int.from_bytes(self.buffer.read(2), 'big')
            extension_length = int.from_bytes(self.buffer.read(2), 'big')
            extension_data = self.buffer.read(extension_length)
            if extension_type == 0x00: # SNI
                self.sni = extension_data[5:].decode("utf-8")
            extensions.append((extension_type, extension_data))
            current_extension_cur += extension_length + 4

    def seek(self, length: int):
        self.buffer.read(length)
    
    def get_sni(self):
        return self.sni

def get_xff(x_forwarded_for: str, index: int = 1):
    addresses = x_forwarded_for.split(",")
    index -= 1
    if not addresses:
        return None
    return addresses[min(len(addresses) - 1, index)].strip()

@web.middleware
async def middleware(request: web.Request, handler: Any) -> web.Response:
    global qps
    qps += 1
    old_app = request.match_info.current_app
    try:
        request.match_info.current_app = app
        address = request.remote or ""
        try:
            address = find_origin_ip(request._transport_peername)[0]
            setattr(request, "address", address)
        except:
            logger.debug(request._transport_peername, request.remote)
        try:
            address = get_xff(request.headers.get("X-Forwarded-For", ""), xff) or address
        except:
            pass
        setattr(request, "custom_address", address)
        start = time.monotonic_ns()
        resp = None
        try:
            resp = await handler(request)
            return resp
        finally:
            status = 500
            if isinstance(request.match_info.route, SystemRoute):
                status = request.match_info.route.status
            if resp is not None:
                if isinstance(resp, web.StreamResponse):
                    status = resp.status
            if request.http_range.start is not None and status == 200:
                status = 206
            end = time.monotonic_ns()
            logger.tdebug("web.debug.request_info", time=units.format_count_time(end - start, 4).rjust(16), host=request.host, address=(address).rjust(16), user_agent=request.headers.get("User-Agent"), real_path=request.raw_path, method=request.method.ljust(9), status=status)
    finally:
        request.match_info.current_app = old_app
REQUEST_BUFFER = 4096
IO_BUFFER = 16384
FINDING_FILTER = "127.0.0.1"
CHECK_PORT_SECRET = os.urandom(8)
ip_tables: dict[tuple[str, int], tuple[str, int]] = {}

def find_origin_ip(target: tuple[str, int]):
    if target not in ip_tables:
        return target
    return find_origin_ip(ip_tables[target])

@dataclass
class IPAddressTable:
    origin: tuple[str, int]
    target: tuple[str, int]
    def __enter__(self):
        ip_tables[self.target] = self.origin
        return self
    
    def __exit__(self, _, __, ___):
        if self.target in ip_tables:
            ip_tables.pop(self.target)
        return self


routes = web.RouteTableDef()

app = web.Application(
    middlewares=[
        middleware
    ]
)
runner: Optional[web.AppRunner] = None
site: Optional[web.TCPSite] = None
public_server: Optional[asyncio.Server] = None
private_ssl_server: Optional[asyncio.Server] = None
private_ssl: Optional[tuple[ssl.SSLContext, ssl.SSLContext]] = None

async def close_writer(writer: asyncio.StreamWriter):
    if writer.is_closing():
        return
    writer.close()
    await writer.wait_closed()

async def get_free_port():
    async def _(_, __):
        ...
    server = await asyncio.start_server(_, port=0)
    port = server.sockets[0].getsockname()[1]
    server.close()
    await server.wait_closed()
    return port

async def forward_data(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    while not writer.is_closing():
        data = await reader.read(IO_BUFFER)
        if not data:
            break
        writer.write(data)
        await writer.drain()
    writer.close()
    await writer.wait_closed()

async def open_forward_data(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, target_ip: str, target_port: int, data: bytes = b''):
    try:
        target_r, target_w = await asyncio.wait_for(
            asyncio.open_connection(
                target_ip,
                target_port
            ), 5
        )
        with IPAddressTable(
            writer.get_extra_info("peername"),
            target_w.get_extra_info("sockname")
        ):
            target_w.write(data)
            await target_w.drain()
            await asyncio.gather(*(
                forward_data(
                    reader, target_w
                )
                ,
                forward_data(
                    target_r, writer
                )

            ))
    except:
        ...
    finally:
        if "target_w" in locals():
            target_w.close()
            await target_w.wait_closed()
        writer.close()
        await writer.wait_closed()

async def public_handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        data = await reader.read(REQUEST_BUFFER)
        if data == CHECK_PORT_SECRET:
            writer.write(data)
            await writer.drain()
            return
        client_ssl = False
        try:
            SNIHelper(data)
            client_ssl = True
        except:
            ...
        if client_ssl:
            if private_ssl_server is None:
                return
            await open_forward_data(
                reader, writer, "127.0.0.1", private_ssl_server.sockets[0].getsockname()[1], data
            )
        else:
            if site is None:
                return
            await open_forward_data(
                reader, writer, "127.0.0.1", site._port, data
            )
    except:
        ...
    finally:
        writer.close()
    ...

async def ssl_handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        if site is None:
           return
        await open_forward_data(
            reader, writer, "127.0.0.1", site._port
        )
    except:
        ...
    finally:
        writer.close()

async def _check_server(ip: str, port: int):
    try:
        r, w = await asyncio.wait_for(asyncio.open_connection(ip, port), 5)
        w.close()
        await asyncio.wait_for(w.wait_closed(), 10)
        return True
    except:
        logger.ttraceback("web.traceback.check_server", port=port)
        return False

async def check_server():
    global site, public_server, private_ssl_server
    servers = [
    ]
    if site is not None:
        servers.append(
            ("127.0.0.1", site._port, start_tcp_site)
        )
    if public_server is not None:
        servers.append(
            ("127.0.0.1", config.const.public_port, start_public_server)
        )
    if private_ssl_server is not None:
        servers.append(
            ("127.0.0.1", private_ssl_server.sockets[0].getsockname()[1], _start_ssl_server)
        )
    result = await asyncio.gather(*(
        _check_server(server[0], server[1]) for server in servers
    ))
    for i, r in enumerate(result):
        if not r:
            await servers[i][2]()
            logger.twarning("web.warning.server_down", server=servers[i][0], port=servers[i][1])

async def start_tcp_site():
    global site, runner
    if runner is None:
        return
    port = await get_free_port()
    if site is not None:
        await site.stop()
    site = web.TCPSite(runner, '127.0.0.1', port)
    await site.start()
    logger.tdebug("web.debug.local_port", port=site._port)

async def init():
    global runner, site, public_server, routes, app

    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()

    await start_tcp_site()

    await start_public_server()

    scheduler.run_repeat_later(check_server, 5, 5)

async def start_public_server():
    global public_server
    if public_server is not None:
        public_server.close()
        await public_server.wait_closed()
    public_server = await asyncio.start_server(
        public_handle, host='0.0.0.0',port=config.const.public_port
    )
    logger.tsuccess("web.success.public_port", port=config.const.public_port)

async def start_ssl_server(cert: Path, key: Path):
    global private_ssl_server, private_ssl
    context = ssl.create_default_context(
        ssl.Purpose.CLIENT_AUTH
    )
    context.load_cert_chain(cert, key)
    context.hostname_checks_common_name = False
    context.check_hostname = False

    client = ssl.create_default_context(
        ssl.Purpose.SERVER_AUTH
    )
    client.load_verify_locations(cert)
    client.hostname_checks_common_name = False
    client.check_hostname = False
    private_ssl = (
        context,
        client
    )
    
    await _start_ssl_server()

async def _start_ssl_server():
    global private_ssl_server, private_ssl
    if not private_ssl:
        return
    if private_ssl_server is not None and private_ssl_server.is_serving():
        private_ssl_server.close()
        await private_ssl_server.wait_closed()
    port = await get_free_port()
    private_ssl_server = await asyncio.start_server(
        ssl_handle,
        '127.0.0.1',
        port,
        ssl=private_ssl[0]
    )
    logger.tdebug("web.debug.ssl_port", port=private_ssl_server.sockets[0].getsockname()[1])


async def unload():
    global app
    await app.cleanup()
    await app.shutdown()