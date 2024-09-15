import asyncio
import io
from pathlib import Path
import time
from typing import Any, Optional
from aiohttp import web
from aiohttp.web_urldispatcher import SystemRoute

from . import units
from . import config
from .logger import logger
import ssl

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

@web.middleware
async def middleware(request: web.Request, handler: Any) -> web.Response:
    with request.match_info.set_current_app(app):
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
            end = time.monotonic_ns()
            logger.tdebug("web.debug.request_info", time=units.format_count_time(end - start, 4).rjust(16), host=request.host, address=(request.remote or "").rjust(16), user_agent=request.headers.get("User-Agent"), real_path=request.raw_path, method=request.method.ljust(9), status=status)

REQUEST_BUFFER = 4096
IO_BUFFER = 16384

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


async def open_forward_data(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, target_ip: str, target_port: int, data: bytes = b''):
    try:
        target_r, target_w = await asyncio.wait_for(
            asyncio.open_connection(
                target_ip,
                target_port
            ), 5
        )
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
        writer.close()

async def public_handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        data = await reader.read(REQUEST_BUFFER)
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
    if site is None:
        return
    await open_forward_data(
        reader, writer, "127.0.0.1", site._port
    )

async def init():
    global runner, site, public_server, routes, app

    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()

    port = await get_free_port()

    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    logger.tdebug("web.debug.local_port", port=site._port)


    public_server = await asyncio.start_server(
        public_handle, port=config.const.public_port
    )
    logger.tsuccess("web.success.public_port", port=config.const.public_port)


async def start_ssl_server(cert: Path, key: Path):
    global private_ssl_server
    context = ssl.create_default_context(
        ssl.Purpose.CLIENT_AUTH
    )
    context.load_cert_chain(cert, key)
    context.hostname_checks_common_name = False
    context.check_hostname = False
    
    if private_ssl_server is not None and private_ssl_server.is_serving():
        private_ssl_server.close()
        await private_ssl_server.wait_closed()
    port = await get_free_port()
    private_ssl_server = await asyncio.start_server(
        ssl_handle,
        '127.0.0.1',
        port,
        ssl=context
    )
    logger.tdebug("web.debug.ssl_port", port=private_ssl_server.sockets[0].getsockname()[1])



async def unload():
    global app
    await app.cleanup()
    await app.shutdown()