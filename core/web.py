import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
import io
import os
from pathlib import Path
import socket
import ssl
import time
from typing import Any, Coroutine, Optional, Callable
from aiohttp import web
from aiohttp.web_urldispatcher import SystemRoute
from tqdm import tqdm

from core import config, scheduler, units, utils
from .logger import logger

from cryptography import x509
from cryptography.x509.oid import NameOID


@dataclass
class CheckServer:
    object: Any
    port: Optional[int]
    start_handle: Callable
    client: Optional[ssl.SSLContext] = None
    args: tuple[Any, ...] = ()

    def __hash__(self) -> int:
        return hash(self.object)

@dataclass
class PrivateSSLServer:
    server: asyncio.Server
    cert: ssl.SSLContext
    key: ssl.SSLContext
    domains: list[str]

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
    time_qps[int(utils.get_runtime())] += 1
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
        start = time.perf_counter_ns()
        resp: web.Response = None # type: ignore
        try:
            resp = await asyncio.create_task(handler(request))
            #if not isinstance(resp, web.WebSocketResponse):
            #    if not resp.prepared:
            #        await resp.prepare(request)
            #await resp.write_eof()
            #resp.force_close()
            #resp.force_close()
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
            end = time.perf_counter_ns()
            logger.tdebug("web.debug.request_info", time=units.format_count_time(end - start, 4).rjust(16), host=request.host, address=(address).rjust(16), user_agent=request.headers.get("User-Agent"), real_path=request.raw_path, method=request.method.ljust(9), status=status)
    finally:
        request.match_info.current_app = old_app
REQUEST_BUFFER = 4096
IO_BUFFER = 16384
FINDING_FILTER = "127.0.0.1"
CHECK_PORT_SECRET = os.urandom(8)
ip_tables: dict[tuple[str, int], tuple[str, int]] = {}
ip_count: defaultdict[tuple[str, int], int] = defaultdict(int)
app = web.Application(
    middlewares=[
        middleware
    ]
)
routes = web.RouteTableDef()

runner: Optional[web.AppRunner] = None
site: Optional[web.TCPSite] = None
public_servers: deque[asyncio.Server] = deque()
privates: dict[tuple[str, str], PrivateSSLServer] = {}

time_qps: defaultdict[int, int] = defaultdict(int)
xff: int = config.const.xff

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
        ip_count[self.origin] += 1
        return self
    
    def __exit__(self, _, __, ___):
        ip_count[self.origin] -= 1
        if ip_count[self.origin] == 0 and self.target in ip_tables:
            ip_tables.pop(self.target)
        return self

async def get_free_port():
    async def _(_, __):
        ...
    server = await asyncio.start_server(_, port=0)
    port = server.sockets[0].getsockname()[1]
    server.close()
    await server.wait_closed()
    return port

async def start_tcp_site():
    global runner, site
    if runner is None:
        return
    if site is not None:
        await site.stop()
    
    port = await get_free_port()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def init():
    global runner, site

    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()

    await start_tcp_site()

    await start_public_server()

    scheduler.run_repeat_later(
        check_server,
        5,
        5
    )

async def forward_data(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    while not writer.is_closing():
        data = await reader.read(IO_BUFFER)
        if not data:
            break
        writer.write(data)
        await writer.drain()
    await close_writer(writer)

async def close_writer(writer: asyncio.StreamWriter):
    if writer.is_closing():
        return
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
            await close_writer(target_w)
        await close_writer(writer)

async def public_handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global privates, site
    try:
        data = await reader.read(REQUEST_BUFFER)
        if data == CHECK_PORT_SECRET:
            writer.write(data)
            await writer.drain()
            return
        client_ssl = False
        domain = None
        try:
            sni = SNIHelper(data)
            domain = sni.get_sni()
            client_ssl = True
        except:
            ...
        if not client_ssl:
            if site is None:
                return
            await open_forward_data(
                reader, writer, "127.0.0.1", site._port, data
            )
        elif privates:
            server = None
            if domain is not None:
                for s in privates.values():
                    for d in s.domains:
                        if d == domain or domain.endswith(d.lstrip("*")):
                            server = s
                            break
            if server is None:
                server = list(privates.values())[0]
            await open_forward_data(
                reader, writer, "127.0.0.1", server.server.sockets[0].getsockname()[1], data
            )
    except:
        ...
    finally:
        writer.close()
    ...

async def start_public_server(count: int = config.const.web_sockets):
    global public_servers
    removes = []
    for server in public_servers:
        if not server.is_serving() or len(server.sockets) == 0:
            server.close()
            try:
                await asyncio.wait_for(server.wait_closed(), timeout=5)
            except:
                ...
            removes.append(server)
    for server in removes:
        public_servers.remove(server)
    port = 0
    async def _start():
        nonlocal port
        port = get_public_port()
        if port == 0:
            port = await get_free_port()

        server = await create_server(public_handle, '0.0.0.0', port)

        await server.start_serving()
        public_servers.append(server)
    def start():
        nonlocal _start
        return asyncio.gather(*(
            asyncio.create_task(_start()) for _ in range(count - len(public_servers))
        ))
    if port == 0:
        public_servers.clear()
        await start()
    logger.tsuccess("web.success.public_port", port=port, current=len(public_servers), total=count)


def get_public_port():
    port = int(config.const.port)
    if port < 0:
        port = int(config.const.public_port)
    if port < 0:
        port = 0
    return port

async def private_handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
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

async def start_private_server(
    cert: Path,
    key: Path,
):
    private_key = (str(cert), str(key))
    if private_key in privates:
        current = privates[private_key]
        context = current.cert
        client = current.key
        domains = current.domains
        current.server.close()
        try:
            await asyncio.wait_for(current.server.wait_closed(), timeout=5)
        except:
            ...
    else:
        domains = get_certificate_domains(cert)
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
    _server = await create_server(
        private_handle,
        '0.0.0.0',
        await get_free_port(),
        ssl=context
    )
    await _server.start_serving()
    privates[private_key] = PrivateSSLServer(
        _server,
        context,
        client,
        domains,
    )
    logger.tdebug("web.debug.ssl_port", port=_server.sockets[0].getsockname()[1])

def get_certificate_domains(
    cert: Path
) -> list[str]:
    certificate = x509.load_pem_x509_certificate(cert.read_bytes())
    content = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    results = [
        item.value if isinstance(item.value, str) else str(item.value)
        for item in content
    ]
    return results

async def check_server():
    servers: list[CheckServer] = []
    if site is not None:
        servers.append(CheckServer(site, site._port, start_tcp_site))
    if public_servers:
        server = public_servers[0]
        servers.append(CheckServer(server, get_server_port(server), start_public_server))
    if privates:
        for hash, server in privates.items():
            servers.append(CheckServer(server.server, get_server_port(server.server), start_private_server, server.key, (
                Path(hash[0]),
                Path(hash[1])
            )))
    servers = list(set(servers))
    
    #logger.tdebug("web.debug.check_server", servers=len(servers))
    results = await asyncio.gather(*[asyncio.create_task(_check_server(server)) for server in servers])
    for server, result in zip(servers, results):
        if result:
            continue
        logger.twarning("web.warning.server_down", port=server.port)
        await server.start_handle()

def get_server_port(server: Optional[asyncio.Server]):
    if server is None:
        return None
    if not server.sockets:
        return None
    try:
        return server.sockets[0].getsockname()[1]
    except:
        return None

async def _check_server(
    server: CheckServer
):
    if server.port is None:
        return False
    if isinstance(server.object, asyncio.Server):
        if len(server.object.sockets) != 0:
            return True
    @utils.retry()
    async def _check():
        r, w = await asyncio.wait_for(
            asyncio.open_connection(
                '127.0.0.1',
                server.port,
                ssl=server.client
            ),
            timeout=5
        )
        w.close()
        try:
            await asyncio.wait_for(w.wait_closed(), timeout=2)
        except:
            ...
    try:
        await _check()
        return True
    except:
        logger.ttraceback("web.traceback.check_server", port=server.port)
    return False

async def unload():
    await app.cleanup()
    await app.shutdown()


ACCEPTHANDLER = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Coroutine]


class TCPServer(
    asyncio.BaseProtocol
):
    def __init__(self, handle: ACCEPTHANDLER) -> None:
        self.handle = handle
        self._loop = asyncio.get_running_loop()
        self._last = time.monotonic()

    def __call__(self):
        return TCPClient(
            self, _loop=self._loop
        )

class TCPClient(
    asyncio.BaseProtocol
):
    def __init__(self, manager: TCPServer, _loop: asyncio.AbstractEventLoop) -> None:
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.manager = manager
        self._loop = asyncio.get_running_loop()
        self.handle_task: Optional[asyncio.Task] = None

    
    def connection_made(self, transport: asyncio.Transport) -> None:
        self.transport = transport
        self.reader = asyncio.StreamReader()
        self.writer = asyncio.StreamWriter(
            transport, protocol=self, reader=self.reader, loop=self._loop
        )
        self.handle_task = self._loop.create_task(self.manager.handle(self.reader, self.writer))

    async def _drain_helper(self):
        ...


    def connection_lost(self, exc: Exception | None) -> None:
        if self.writer is not None:
            self.writer.close()
            self.writer = None
        if self.handle_task is not None:
            self.handle_task.cancel()
            self.handle_task = None
        self.reader = None
        self.transport = None

    def data_received(self, data: bytes) -> None:
        if self.writer is None or self.reader is None:
            return
        self.reader.feed_data(data)

    def eof_received(self) -> bool:
        return False
    
    def __del__(self):
        if self.writer is not None:
            self.writer.close()
            self.writer = None
        if self.handle_task is not None:
            self.handle_task.cancel()
            self.handle_task = None
        self.reader = None
        self.transport = None


async def create_server(
    handle: ACCEPTHANDLER,
    host=None, port=None,
    *, family=socket.AF_UNSPEC,
    flags=socket.AI_PASSIVE, backlog=config.const.backlog,
    ssl=None, reuse_address=True, reuse_port=None,
    ssl_handshake_timeout=None,
    ssl_shutdown_timeout=None,
):
    server = await asyncio.get_event_loop().create_server(
        TCPServer(handle),
        host=host,
        port=port,
        family=family,
        flags=flags,
        backlog=backlog,
        ssl=ssl,
        reuse_address=reuse_address,
        reuse_port=reuse_port,
        ssl_handshake_timeout=ssl_handshake_timeout,
        ssl_shutdown_timeout=ssl_shutdown_timeout,
    )
    return server