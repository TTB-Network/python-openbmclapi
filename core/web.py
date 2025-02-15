from collections import defaultdict
import ssl
import anyio
import anyio.abc
import anyio.streams
import anyio.streams.tls
import fastapi
import uvicorn

from . import utils, abc
from .logger import logger
from .config import cfg
from .locale import t
from .cluster import ClusterManager

class ForwardAddress:
    def __init__(
        self,
        sockname: tuple[str, int],
        peername: tuple[str, int],
    ):
        self.sockname = sockname
        self.peername = peername

    def __enter__(self):
        forwards_count[self.sockname] += 1
        forwards[self.sockname] = self.peername
        return self

    def __exit__(self, *args):
        forwards_count[self.sockname] -= 1
        if forwards_count[self.sockname] == 0:
            del forwards[self.sockname]
            del forwards_count[self.sockname]

app = fastapi.FastAPI(
    redoc_url=None,
    docs_url=None,
    openapi_url=None,
)
http_port = -1
certificates: list[abc.Certificate] = []
tls_ports: dict[str, int] = {}
forwards: dict[tuple[str, int], tuple[str, int]] = {}
forwards_count: defaultdict[tuple[str, int], int] = defaultdict(int)

async def get_free_port():
    listener = await anyio.create_tcp_listener()
    port = listener.extra(anyio.abc.SocketAttribute.local_port)
    return port

async def pub_listener():
    global pub_port
    pub_port = cfg.web_port
    if pub_port == -1:
        pub_port = cfg.web_public_port
    if pub_port == -1:
        raise RuntimeError(t("error.web.forward.pub_port", port=pub_port))
    listener = await anyio.create_tcp_listener(
        local_port=pub_port,
    )
    async with listener:
        logger.tinfo("web.forward.pub_port", port=pub_port)
        await listener.serve(pub_handler)

async def pub_handler(
    sock: anyio.abc.SocketStream
):
    try:
        async with sock:
            # first read 16384 bytes of tls
            buf = await sock.receive(16384)
            handshake = utils.parse_tls_handshake(buf)
            port = None
            if handshake is None:
                port = http_port
            else:
                if handshake.sni in tls_ports:
                    port = tls_ports[handshake.sni]
                elif tls_ports:
                    port = list(tls_ports.values())[0]
            if port is None:
                return
            # then forward to port
            await forward(sock, port, buf)
    except (
        anyio.EndOfStream,
        anyio.BrokenResourceError
    ):
        ...
    except Exception as e:
        logger.debug_traceback()

async def tls_listener(
    cert: abc.Certificate
):
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.check_hostname = False
    context.hostname_checks_common_name = False
    context.load_cert_chain(cert.cert, cert.key)
    listener = await anyio.create_tcp_listener(
        local_host="127.0.0.1",
    )
    tls_listener = anyio.streams.tls.TLSListener(listener, context)
    async with tls_listener:
        logger.tdebug("web.forward.tls_port", port=listener.extra(anyio.abc.SocketAttribute.local_port))
        for domain in cert.domains:
            tls_ports[domain] = listener.extra(anyio.abc.SocketAttribute.local_port)
        await tls_listener.serve(tls_handler)

async def tls_handler(
    sock: anyio.streams.tls.TLSStream
):
    try:
        async with sock:
            # first read 16384 bytes of tls
            # then forward to port
            await forward(sock, http_port)
    except (
        anyio.EndOfStream,
        anyio.BrokenResourceError,
        ssl.SSLError,
    ):
        ...
    except Exception as e:
        logger.debug_traceback()

async def forward(
    sock: anyio.abc.SocketStream | anyio.streams.tls.TLSStream,
    port: int,
    buffer: bytes = b''
):
    try:
        async with await anyio.connect_tcp(
            "127.0.0.1",
            port
        ) as conn:
            with ForwardAddress(
                get_sockname(conn),
                get_peername(sock)
            ):
                async with anyio.create_task_group() as task_group:
                    if buffer:
                        await conn.send(buffer)
                    task_group.start_soon(forward_data, sock, conn)
                    task_group.start_soon(forward_data, conn, sock)
    except:
        raise

def get_sockname(
    sock: anyio.abc.SocketStream | anyio.streams.tls.TLSStream
) -> tuple[str, int]:
    return sock.extra(anyio.abc.SocketAttribute.local_address) # type: ignore

def get_peername(
    sock: anyio.abc.SocketStream | anyio.streams.tls.TLSStream
) -> tuple[str, int]:
    return sock.extra(anyio.abc.SocketAttribute.remote_address) # type: ignore

def get_origin_address(
    name: tuple[str, int]
) -> tuple[str, int]:
    if name in forwards:
        return get_origin_address(forwards[name])
    return name

async def forward_data(
    sock: anyio.abc.SocketStream | anyio.streams.tls.TLSStream,
    conn: anyio.abc.SocketStream | anyio.streams.tls.TLSStream
):
    try:
        while 1:
            await conn.send(await sock.receive())
    except:
        try:
            await conn.send_eof()
        except:
            ...

async def setup(
    task_group: anyio.abc.TaskGroup,
    clusters: ClusterManager
):
    global http_port, certificates
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=await get_free_port(),
        log_config={
            "version": 1
        }
    )
    http_port = config.port
    task_group.start_soon(uvicorn.Server(config).serve)

    logger.tdebug("web.uvicorn.port", port=config.port)

    task_group.start_soon(pub_listener)

    cert_type = utils.get_certificate_type()

    if cert_type == abc.CertificateType.PROXY:
        return 
    
    certificates = []
    if cert_type == abc.CertificateType.BYOC:
        certificates.append(abc.Certificate(
            cert_type,
            cfg.get("cert.cert"),
            cfg.get("cert.key")
        ))
    elif cert_type == abc.CertificateType.CLUSTER:
        for cert in await utils.gather(*(
            cluster.request_cert() for cluster in clusters.clusters
        )):
            if cert is None:
                continue
            certificates.append(cert)

    if len(certificates) == 0:
        raise RuntimeError(t("error.web.certificates"))

    for cert in certificates:
        task_group.start_soon(tls_listener, cert)