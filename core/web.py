from collections import defaultdict
import datetime
import ssl
import anyio
import anyio.abc
import anyio.streams
import anyio.streams.tls
import fastapi
import uvicorn
import tianxiu2b2t.anyio.streams as streams
from tianxiu2b2t.anyio import concurrency
from tianxiu2b2t.utils import runtime

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

class QueryPerSecondStatistics:
    def __init__(
        self,
        expires: int = 600
    ):
        self._timer = lambda: runtime.monotonic()
        self._data: defaultdict[int, int] = defaultdict(int)
        self._expires = expires


    def add(self):
        self._data[int(self._timer())] += 1
        self.expire()
    
    def expire(self):
        t = self._timer()
        for k, v in list(self._data.items()):
            if k + self._expires < t:
                del self._data[k]

    def get_all(self) -> dict[datetime.datetime, int]:
        now = datetime.datetime.now().replace(microsecond=0)
        t = self._timer()
        data = {}
        for k, v in self._data.items():
            if k >= t:
                continue
            data[(now - datetime.timedelta(seconds=t - k)).replace(microsecond=0)] += v
        return data
    
    def merge_data(self, interval: int = 5) -> dict[datetime.datetime, int]:
        timestamp = datetime.datetime.fromtimestamp(datetime.datetime.now().timestamp() // interval * interval)
        res: defaultdict[datetime.datetime, int] = defaultdict(int)
        cur = int(self._timer() // interval)
        for k, v in self._data.items():
            c = int(k // interval)
            if c >= cur:
                continue
            res[timestamp - datetime.timedelta(seconds=c * interval)] += v
        return res


app = fastapi.FastAPI(
    redoc_url=None,
    docs_url=None,
    openapi_url=None,
)
http_port = -1
certificates: list[abc.Certificate] = []
tls_listener: streams.AutoTLSListener | None = None
forwards: dict[tuple[str, int], tuple[str, int]] = {}
forwards_count: defaultdict[tuple[str, int], int] = defaultdict(int)
query_per_second_statistics = QueryPerSecondStatistics()

async def get_free_port():
    listener = await anyio.create_tcp_listener()
    port = listener.extra(anyio.abc.SocketAttribute.local_port)
    return port

async def pub_listener(
    task_group: anyio.abc.TaskGroup
):
    global pub_port, tls_listener
    pub_port = cfg.web_port
    if pub_port == -1:
        pub_port = cfg.web_public_port
    if pub_port == -1:
        raise RuntimeError(t("error.web.forward.pub_port", port=pub_port))
    listener = await anyio.create_tcp_listener(
        local_port=pub_port,
    )

    tls_listener = streams.AutoTLSListener(
        streams.FixedSocketListener(
            listener
        ),
    )
    task_group.start_soon(serve, tls_listener)

async def serve(
    listener: streams.AutoTLSListener,
):
    async with listener:
        logger.tinfo("web.forward.pub_port", port=pub_port)
        await listener.serve(pub_handler)

async def pub_handler(
    sock: streams.BufferedByteStream,
    extra: streams.TLSExtraData
):
    try:
        async with sock:
            await forward(sock, http_port, b'')
    except (
        anyio.EndOfStream,
        anyio.BrokenResourceError,
        ssl.SSLError
    ):
        ...
    except Exception as e:
        logger.debug_traceback()

async def forward(
    sock: streams.BufferedByteStream,
    port: int,
    buffer: bytes = b''
):
    try:
        async with streams.BufferedByteStream(
            await anyio.connect_tcp(
            "127.0.0.1",
            port
        )) as conn:
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
    sock: streams.BufferedByteStream
) -> tuple[str, int]:
    return sock.extra(anyio.abc.SocketAttribute.local_address) # type: ignore

def get_peername(
    sock: streams.BufferedByteStream
) -> tuple[str, int]:
    return sock.extra(anyio.abc.SocketAttribute.remote_address) # type: ignore

def get_origin_address(
    name: tuple[str, int]
) -> tuple[str, int]:
    if name in forwards:
        return get_origin_address(forwards[name])
    return name

async def forward_data(
    sock: streams.BufferedByteStream,
    conn: streams.BufferedByteStream
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

    await pub_listener(task_group)

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
        for cert in await concurrency.gather(*(
            cluster.request_cert() for cluster in clusters.clusters
        )):
            if cert is None:
                continue
            certificates.append(cert)

    if len(certificates) == 0:
        raise RuntimeError(t("error.web.certificates"))

    if tls_listener is None:
        raise RuntimeError(t("error.web.tls_listener"))

    for cert in certificates:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(cert.cert, cert.key)
        context.check_hostname = False
        context.hostname_checks_common_name = False
        context.verify_mode = ssl.CERT_NONE
        
        for domain in cert.domains:
            tls_listener.add_context(
                domain,
                context
            )