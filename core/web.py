import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
import io
from pathlib import Path
import random
import ssl
import time
from typing import Any, Optional
from aiohttp.web_urldispatcher import SystemRoute
from aiohttp import web as aiohttp_web
import socket

from cryptography import x509
from cryptography.x509.oid import NameOID

from core import units, utils

from .logger import logger
from . import config

class ClientHandshakeInfo:
    def __init__(self, version: int, sni: Optional[str]):
        self.version = version
        self.sni = sni

    @property
    def version_name(self):
        return SSL_PROTOCOLS.get(self.version, "Unknown")
    
    def __str__(self):
        return f"ClientHandshakeInfo(version={self.version_name}, sni={self.sni})"
    def __repr__(self):
        return str(self)

class Client:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        addr: Optional[tuple[str, int]] = None,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._addr = addr
        self._buffers: deque[bytes] = deque()

    @property
    def address(self) -> tuple[str, int]:
        return self._addr or self._writer.get_extra_info("peername")
    
    def feed_data(self, data: bytes) -> None:
        self._buffers.appendleft(data)

    async def read(self, n: int) -> bytes:
        if self._buffers:
            buffer = self._buffers.popleft()
            if len(buffer) > n:
                self._buffers.appendleft(buffer[n:])
                return buffer[:n]
            else:
                return buffer
        return await self._reader.read(n)

    async def write(self, data: bytes) -> None:
        self._writer.write(data)
        await self._writer.drain()

    async def close(self) -> None:
        self._writer.close()
        await self._writer.wait_closed()

    @property
    def is_closing(self):
        return self._writer.is_closing()

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

SSL_PROTOCOLS = {
    0x0301: "TLSv1.0",
    0x0302: "TLSv1.1",
    0x0303: "TLSv1.2",
    0x0304: "TLSv1.3",
}
WHITELIST_PATHS = [
    "/download/",
    "/measure/"
]
ALLOW_IP = [
    "127.0.0.1",
    "::1"
]
DISALLOW_PUBLIC_DASHBOARD: list[int] = [
    500,
    502,
    503,
    504,
    505,
    506,
    507,
    508,
    510,
    511,
    400,
    401,
    402,
    403,
    404,
    405,
    406,
    407,
    408,
    409,
    410,
    411,
    412,
    413,
    414,
    415,
    416,
    417,
    418,
    421,
    422,
    423,
    424,
    426,
    428,
    429,
    431,
    451,
]

@aiohttp_web.middleware
async def middleware(request: aiohttp_web.Request, handler: Any) -> aiohttp_web.Response:
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
            if config.const.proxy:
                try:
                    address = request.headers.get("X-Real-IP") or address
                except:
                    pass
            else:
                address = address
        except:
            pass
        setattr(request, "custom_address", address)
        start = time.perf_counter_ns()
        if config.const.disallow_public_dashboard and address not in ALLOW_IP and not any([request.path.startswith(path) for path in WHITELIST_PATHS]):
            return await asyncio.create_task(special_response())
        resp: aiohttp_web.Response = None # type: ignore
        try:
            resp = await asyncio.create_task(handler(request))
            return resp
        finally:
            status = 500
            if isinstance(request.match_info.route, SystemRoute):
                status = request.match_info.route.status
            if resp is not None:
                if isinstance(resp, aiohttp_web.StreamResponse):
                    status = resp.status
            if request.http_range.start is not None and status == 200:
                status = 206
            end = time.perf_counter_ns()
            logger.tdebug("web.debug.request_info", time=units.format_count_time(end - start, 4).rjust(16), host=request.host, address=(address).rjust(16), user_agent=request.headers.get("User-Agent"), real_path=request.raw_path, method=request.method.ljust(9), status=status)
    finally:
        request.match_info.current_app = old_app
        


async def special_response():
    if random.randint(0, 100) >= 10:
        await asyncio.sleep(random.randint(30, 180))
    status = random.choice(DISALLOW_PUBLIC_DASHBOARD)
    return aiohttp_web.Response(status=status)



def find_origin_ip(target: tuple[str, int]):
    if target not in ip_tables:
        return target
    return find_origin_ip(ip_tables[target])

async def _forward(
    from_conn: Client,
    to_conn: Client
):
    while not from_conn.is_closing and (data := await from_conn.read(16384)):
        if not data:
            break
        await to_conn.write(data)
    
async def forward(
    from_conn: Client,
    target_port: int,
):
    try:
        conn = Client(
            *await asyncio.wait_for(
                asyncio.open_connection(
                    host="127.0.0.1",
                    port=target_port,
                ),
                timeout=5,
            )
        )
        with IPAddressTable(
            from_conn.address,
            conn._writer.get_extra_info("sockname")[0],
        ):
            try:
                await asyncio.gather(
                    _forward(from_conn, conn),
                    _forward(conn, from_conn),
                )
            except asyncio.TimeoutError:
                conn._writer.close()
    except:
        logger.traceback(target_port)
        return
    
async def start_tcp_site():
    global site, runner

    if runner is None:
        raise RuntimeError("Runner is not initialized")

    port = await get_free_port()
    site = aiohttp_web.TCPSite(runner, host="127.0.0.1", port=port, **asyncio_server_cfg)
    await site.start()
    logger.tdebug("web.debug.tcp_site", port=port)

async def public_handle(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter
):
    client = Client(reader, writer)
    buffer = await client.read(16384)
    info = get_client_handshake_info(buffer)
    client.feed_data(buffer)
    try:
        port: Optional[int] = None
        if (info.version == -1 or info.sni is None) and site is not None:
            port = site._port

        if info.version != -1 and info.sni is not None:
            context = None
            if info.sni in sni_contexts:
                context = sni_contexts[info.sni]
            if context is None and sni_contexts:
                context = list(sni_contexts.values())[0]
            if context is not None:
                port = private_servers[context].sockets[0].getsockname()[1]
        if port is not None:
            await forward(client, port)
        else:
            logger.debug("Not found", info)

    except (
        GeneratorExit,
        ConnectionAbortedError,
        asyncio.TimeoutError,
        asyncio.CancelledError
    ):
        pass
    except:
        logger.traceback()
        pass
    finally:
        writer.close()
        if client.is_closing:
            return
        try:
            await writer.wait_closed()
        except:
            pass

    
async def private_handle(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter
):
    if site is not None:
        await forward(Client(reader, writer), site._port)
    writer.close()
    try:
        await writer.wait_closed()
    except:
        pass

async def start_private_server(
    crtfile: Path,
    keyfile: Path
):
    key = (crtfile, keyfile)
    if key in ssl_contexts:
        context = ssl_contexts[key]
        if context in private_servers:
            private_servers[context].close()
            await private_servers[context].wait_closed()
        del private_servers[context]
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(crtfile, keyfile)
    context.hostname_checks_common_name = False
    context.check_hostname = False
    ssl_contexts[key] = context

    domains = get_certificate_domains(crtfile)
    for domain in domains:
        sni_contexts[domain] = context

    server = await asyncio.start_server(
        private_handle,
        port=0,
        ssl=context,
        **asyncio_server_cfg
    )
    await server.start_serving()
    logger.tdebug("web.debug.ssl_port", port=server.sockets[0].getsockname()[1])
    private_servers[context] = server

async def get_free_port():
    async def _(_, __):
        ...
    server = await asyncio.start_server(_, port=0)
    port = server.sockets[0].getsockname()[1]
    server.close()
    await server.wait_closed()
    return port

def get_public_port():
    port = int(config.const.port)
    if port < 0:
        port = int(config.const.public_port)
    if port < 0:
        port = 0
    return port

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

async def _start_public_server(port: int):
    server = await asyncio.start_server(
        public_handle,
        port=port,
        **asyncio_server_cfg
    )
    public_servers.append(server)
    await server.start_serving()

async def start_public_server():
    count = 1
    if hasattr(socket, "SO_REUSEPORT") or hasattr(socket, "SO_REUSEADDR"):
        count = socket_count
    port = get_public_port()
    await asyncio.gather(*(_start_public_server(port) for _ in range(count)))
    logger.tsuccess("web.success.public_port", port=port, current=len(public_servers), total=count)


async def init():
    global runner, site


    app.add_routes(routes)
    runner = aiohttp_web.AppRunner(app)
    await runner.setup()

    await start_tcp_site()

    await start_public_server()

async def unload():
    await app.cleanup()
    await app.shutdown()

    for server in public_servers:
        server.close()
    for server in private_servers.values():
        server.close()


def get_client_handshake_info(data: bytes):
    info = ClientHandshakeInfo(-1, None)
    try:
        buffer = io.BytesIO(data)
        if not buffer.read(1):
            raise
        info.version = int.from_bytes(buffer.read(2), 'big')
        if not buffer.read(40):
            raise
        buffer.read(buffer.read(1)[0])
        buffer.read(int.from_bytes(buffer.read(2), 'big'))
        buffer.read(buffer.read(1)[0])
        extensions_length = int.from_bytes(buffer.read(2), 'big')
        current_extension_cur = 0
        extensions = []
        while current_extension_cur < extensions_length:
            extension_type = int.from_bytes(buffer.read(2), 'big')
            extension_length = int.from_bytes(buffer.read(2), 'big')
            extension_data = buffer.read(extension_length)
            if extension_type == 0x00: # SNI
                info.sni = extension_data[5:].decode("utf-8")
            extensions.append((extension_type, extension_data))
            current_extension_cur += extension_length + 4
    except:
        ...
    return info

app = aiohttp_web.Application(
    middlewares=[
        middleware
    ]
)
routes = aiohttp_web.RouteTableDef()
ip_tables: dict[tuple[str, int], tuple[str, int]] = {}
ip_count: defaultdict[tuple[str, int], int] = defaultdict(int)
time_qps: defaultdict[int, int] = defaultdict(int)
socket_count = config.const.web_sockets
public_servers: deque[asyncio.Server] = deque()
public_server_tasks: deque[asyncio.Task] = deque()
private_server_tasks: deque[asyncio.Task] = deque()
site: Optional[aiohttp_web.TCPSite] = None
runner: Optional[aiohttp_web.AppRunner] = None
ssl_contexts: dict[tuple[Path, Path], ssl.SSLContext] = {}
private_servers: dict[ssl.SSLContext, asyncio.Server] = {}
sni_contexts: dict[str, ssl.SSLContext] = {}
asyncio_server_cfg: dict[str, Any] = {
    "backlog": config.const.backlog,
}

if hasattr(socket, "SO_REUSEADDR"):
    asyncio_server_cfg["reuse_address"] = True
if hasattr(socket, "SO_REUSEPORT"):
    asyncio_server_cfg["reuse_port"] = True
