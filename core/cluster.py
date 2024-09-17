import abc
import asyncio
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
import hashlib
import hmac
import io
from pathlib import Path
import time
from typing import Any, Callable, Coroutine, Optional
import aiohttp.client_exceptions
import pyzstd as zstd
import aiohttp
from tqdm import tqdm

from . import web
from . import utils, logger, config, scheduler, units, storages, i18n
from .storages import File as SFile
import socketio

@dataclass
class Token:
    last: float
    token: str
    ttl: float

@dataclass
class File:
    path: str
    hash: str
    size: int
    mtime: int

    def __hash__(self) -> int:
        return hash((self.hash, self.size, self.mtime))

class StorageManager:
    def __init__(self, clusters: 'ClusterManager'):
        self.clusters = clusters
        self.storages: deque[storages.iStorage] = deque()
        self.available_storages: deque[storages.iStorage] = deque()
        self.check_available: utils.CountLock = utils.CountLock()

        self.check_available.acquire()

        self.check_type_file = "exists+size"

    def init(self):
        scheduler.run_repeat(self._check_available, 120)

    async def _check_available(self):
        for storage in self.storages:
            if not await storage.exists(CHECK_FILE_MD5):
                await storage.write_file(
                    convert_file_to_storage_file(CHECK_FILE),
                    CHECK_FILE_CONTENT.encode("utf-8"),
                    CHECK_FILE.mtime
                )
            if await storage.get_size(CHECK_FILE_MD5) == len(CHECK_FILE_CONTENT):
                self.available_storages.append(storage)
        if len(self.available_storages) > 0:
            self.check_available.release()
        else:
            self.check_available.acquire()

    def add_storage(self, storage: storages.iStorage):
        self.storages.append(storage)

    async def available(self):
        await self.check_available.wait()
        return len(self.available_storages) > 0
    
    async def write_file(self, file: File, content: bytes):
        return all(await asyncio.gather(*(asyncio.create_task(storage.write_file(convert_file_to_storage_file(file), content, file.mtime)) for storage in self.available_storages)))

    async def get_missing_files(self, files: set[File]) -> set[File | Any]:
        async def _(file: File, storage: storages.iStorage):
            return True
        function = _
        if function is None:
            logger.twarning("cluster.warning.no_check_function")
            function = self._check_exists
        with tqdm(
            total=len(files) * len(self.available_storages),
            desc="Checking files",
            unit="file",
            unit_scale=True,
        ) as pbar:
            missing_files = set()
            waiting_files: asyncio.Queue[File] = asyncio.Queue()
            
            for file in files:
                waiting_files.put_nowait(file)
            
            await asyncio.gather(*(self._get_missing_file_storage(function, missing_files, waiting_files, storage, pbar) for storage in self.available_storages))
            return missing_files or set()
    
    async def _get_missing_file_storage(self, function: Callable[..., Coroutine[Any, Any, bool]], missing_files: set[File], files: asyncio.Queue[File], storage: storages.iStorage, pbar: tqdm):
        while not files.empty():
            file = await files.get()
            if await function(file, storage):
                pbar.update(1)
            else:
                missing_files.add(file)
            files.task_done()
            await asyncio.sleep(0)
    
    async def _check_exists(self, file: File, storage: storages.iStorage):
        return await storage.exists(file.hash)
    async def _check_size(self, file: File, storage: storages.iStorage):
        return await self._check_exists(file, storage) and await storage.get_size(file.hash) == file.size
    async def _check_hash(self, file: File, storage: storages.iStorage):
        return await self._check_exists(file, storage) and utils.equals_hash(file.hash, await storage.read_file(file.hash))

    async def get_file(self, hash: str):
        file = None
        if await self.available():
            storage = self.get_width_storage()
            if isinstance(storage, storages.LocalStorage) and await storage.exists(hash):
                return LocalStorageFile(
                    hash,
                    await storage.get_size(hash),
                    await storage.get_mtime(hash),
                    Path(storage.get_path(hash))
                )
            elif isinstance(storage, storages.AlistStorage):
                return URLStorageFile(
                    hash,
                    await storage.get_size(hash),
                    await storage.get_mtime(hash),
                    await storage.get_url(hash)
                )
                ...
        if file is None:
            async with aiohttp.ClientSession(
                config.const.base_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Authorization": await self.clusters.clusters[0].get_token()
                }
            ) as session:
                async with session.get(
                    f"/openbmclapi/download/{hash}"
                ) as resp:
                    file = MemoryStorageFile(
                        hash,
                        resp.content_length or -1,
                        time.time(),
                        await resp.content.read()
                    )
        return file

    def get_width_storage(self, c_storage: Optional[storages.iStorage] = None) -> storages.iStorage:
        current_storage = self.available_storages[0]
        if current_storage.current_width > current_storage.width:
            current_storage.current_width += 1
            return current_storage
        else:
            self.available_storages.remove(current_storage)
            self.available_storages.append(current_storage)
            if c_storage is not None:
                return c_storage
            return self.get_width_storage(c_storage=c_storage or current_storage)


@dataclass
class OpenBMCLAPIConfiguration:
    source: str
    concurrency: int

class DownloadStatistics:
    def __init__(self, total: int = 0, size: int = 0):
        self.total_size = size
        self.total_files = total
        self.downloaded_files = 0
        self.failed_files = 0
        self.pbar = None
    
    def __enter__(self):
        self.pbar = tqdm(
            total=self.total_size,
            unit="b",
            unit_scale=True,
            unit_divisor=1024,
            desc=i18n.locale.t("cluster.processbar.download_files")
        )
        self.downloaded_files = 0
        self.failed_files = 0
        return self

    def update(self, n: float):
        if self.pbar is None:
            return
        self.pbar.update(n)

    def update_success(self):
        if self.pbar is None:
            return
        self.downloaded_files += 1
        self.pbar.set_postfix_str(
            f"{self.downloaded_files}/{self.total_files} ({self.failed_files} failed)"
        )

    def update_failed(self):
        if self.pbar is None:
            return
        self.failed_files += 1
        self.pbar.set_postfix_str(
            f"{self.downloaded_files}/{self.total_files} ({self.failed_files} failed)"
        )

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.pbar is None:
            return
        self.pbar.close()

class FileListManager:
    def __init__(self, clusters: 'ClusterManager'):
        self.clusters = clusters
        self.cluster_last_modified: defaultdict['Cluster', int] = defaultdict(lambda: 0)
        self.sync_sem: utils.SemaphoreLock = utils.SemaphoreLock(256)
        self.download_statistics = DownloadStatistics()

    async def _get_filelist(self, cluster: 'Cluster'):
        async with aiohttp.ClientSession(
            config.const.base_url,
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {await cluster.get_token()}"
            }
        ) as session:
            async with session.get(
                f"/openbmclapi/files",
                params={
                    "lastModified": str(int(self.cluster_last_modified[cluster]))
                }
            ) as resp:
                resp.raise_for_status()
                if resp.status == 204:
                    return []
                stream = utils.FileStream(zstd.decompress(await resp.read()))
                filelist = [
                    File(
                        path=stream.read_string(),
                        hash=stream.read_string(),
                        size=stream.read_long(),
                        mtime=stream.read_long()
                    )
                    for _ in range(stream.read_long())
                ]
                if filelist:
                    self.cluster_last_modified[cluster] = max(filelist, key=lambda f: f.mtime).mtime
                return filelist

    async def fetch_filelist(self) -> set[File]:
        result_filelist = set().union(*await asyncio.gather(*(asyncio.create_task(self._get_filelist(cluster)) for cluster in self.clusters.clusters)))
        logger.tsuccess("cluster.success.fetch_filelist", total=units.format_number(len(result_filelist)), size=units.format_bytes(sum(f.size for f in result_filelist)))
        return result_filelist

    async def sync(self):
        result = await self.fetch_filelist()

        missing = await self.clusters.storage_manager.get_missing_files(result)

        if not missing:
            logger.tsuccess("cluster.success.no_missing_files")
            return

        await self.clusters.storage_manager.available()
        configurations: defaultdict[str, deque[OpenBMCLAPIConfiguration]] = defaultdict(deque)
        for configuration in await asyncio.gather(*(asyncio.create_task(self._get_configuration(cluster)) for cluster in self.clusters.clusters)):
            for k, v in configuration.items():
                configurations[k].append(v)
        # get better configuration
        configuration = max(configurations.items(), key=lambda x: x[1][0].concurrency)[1][0]
        logger.tinfo("cluster.info.sync_configuration", source=configuration.source, concurrency=configuration.concurrency)
        #self.sync_sem.set_value(configuration.concurrency)

        await self.download(missing)

    async def download(self, filelist: set[File]):
        total = len(filelist)
        size = sum(f.size for f in filelist)
        file_queues = asyncio.Queue()
        for file in filelist:
            await file_queues.put(file)
        sessions = []
        tasks = []
        with DownloadStatistics(
            total=total,
            size=size
        ) as pbar:
            for _ in range(0, max(1, config.const.threads)):
                if _ % 32 == 0:
                    session = aiohttp.ClientSession(
                        config.const.base_url,
                        headers={
                            "User-Agent": USER_AGENT,
                        }
                    )
                    sessions.append(session)
                tasks.append(asyncio.create_task(self._download(session, file_queues, pbar)))
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                return
            finally:
                for session in sessions:
                    await session.close()

    

    async def _download(self, session: aiohttp.ClientSession, file_queues: asyncio.Queue[File], pbar: DownloadStatistics):
        while not file_queues.empty():
            recved = 0
            try:
                file = await file_queues.get()
                content = io.BytesIO()
                async with self.sync_sem:
                    async with session.get(
                        file.path
                    ) as resp:
                        async for chunk in resp.content.iter_any():
                            content.write(chunk)
                            recved += len(chunk)
                            pbar.update(len(chunk))
                # check hash
                hash = utils.get_hash_hexdigest(file.hash, content.getvalue())
                if hash != file.hash:
                    raise ValueError(hash)
                if await self.clusters.storage_manager.write_file(file, content.getvalue()):
                    pbar.update_success()
                else:
                    raise FileNotFoundError()
            except asyncio.CancelledError:
                pbar.update(-recved)
                break
            except Exception as e:
                pbar.update(-recved)
                await file_queues.put(file)
                pbar.update_failed()
                r = None
                if "resp" in locals():
                    r = resp
                self.report(file, e, r)
                continue
            pbar.update_success()

    def report(self, file: File, error: Exception, resp: Optional[aiohttp.ClientResponse] = None):
        msg = error.args
        type = "unknown"
        if isinstance(error, ValueError):
            type = "hash"
        elif isinstance(error, (
            aiohttp.client_exceptions.ClientConnectionError,
            aiohttp.client_exceptions.ClientConnectorError,
            aiohttp.client_exceptions.ServerDisconnectedError,
            aiohttp.client_exceptions.ClientPayloadError,
            aiohttp.client_exceptions.ClientOSError,
            aiohttp.client_exceptions.ClientResponseError,
            aiohttp.client_exceptions.ServerTimeoutError,
            aiohttp.client_exceptions.ClientHttpProxyError,
            aiohttp.client_exceptions.ClientProxyConnectionError,
            aiohttp.client_exceptions.ClientSSLError,
            aiohttp.client_exceptions.ClientConnectorCertificateError,
            aiohttp.client_exceptions.ClientConnectorSSLError,
            OSError
        )):
            type = "network"
        else:
            type = "file"
        responses = []
        host = None
        if resp is not None:
            for r in resp.history:
                responses.append(f"{r.status} | {r.url}")
            responses.append(f"{resp.status} | {resp.url}")
            host = resp.host
        hash = msg[0] if len(msg) > 0 and type == "file" else None
        logger.debug(error)
        logger.terror(f"clusters.error.downloading", type=type, file_hash=file.hash, file_size=units.format_bytes(file.size), host=host, file_path=file.path, hash=hash, responses="\n".join(("", *responses)))


    async def _get_configuration(self, cluster: 'Cluster'):
        async with aiohttp.ClientSession(
            config.const.base_url,
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {await cluster.get_token()}"
            }
        ) as session:
            async with session.get(
                f"/openbmclapi/configuration"
            ) as resp:
                resp.raise_for_status()
                return {
                    k: OpenBMCLAPIConfiguration(**v) for k, v in (await resp.json()).items()
                }

class ClusterManager:
    def __init__(self):
        self.cluster_id_tables: dict[str, 'Cluster'] = {}
        self.file_manager = FileListManager(self)
        self.storage_manager = StorageManager(self)

    def add_cluster(self, cluster: 'Cluster'):
        self.cluster_id_tables[cluster.id] = cluster

    @property
    def clusters(self):
        return list(self.cluster_id_tables.values())

    async def start(self):
        self.storage_manager.init()
        logger.tdebug("cluster.debug.base_url", base_url=config.const.base_url)
        # check files
        await self.file_manager.sync()

        # start web ssl
        cert = await self.get_certificate()
        await web.start_ssl_server(
            cert.cert, cert.key
        )
        public_port = config.const.public_port
        public_host = cert.host

        logger.tdebug("cluster.debug.public_host", host=public_host, port=public_port)

        # start job

        for cluster in self.clusters:
            await cluster.enable()

    def get_cluster_by_id(self, id: Optional[str] = None) -> Optional['Cluster']:
        return self.cluster_id_tables.get(id or "", None)


    async def get_certificate(self):
        main = ClusterCertificate(
            config.const.host,
            Path(config.const.ssl_cert),
            Path(config.const.ssl_key)
        )
        if main.is_valid:
            return main
        await asyncio.gather(*[cluster.request_cert() for cluster in self.clusters])
        return [cluster.certificate for cluster in self.clusters][0]
    
    async def stop(self):
        await asyncio.gather(*[cluster.disable(True) for cluster in self.clusters])
        await asyncio.gather(*[cluster.socket_io.disconnect() for cluster in self.clusters])

@dataclass
class ClusterCounter:
    hits: int = 0
    bytes: int = 0

    def __sub__(self, object: 'ClusterCounter'):
        self.hits -= object.hits
        self.bytes -= object.bytes
        return self

    def clone(self):
        return ClusterCounter(
            self.hits,
            self.bytes
        )
    
    def __repr__(self) -> str:
        return f"ClusterCounter(hits={self.hits}, bytes={self.bytes})"
    
    def __str__(self) -> str:
        return f"ClusterCounter(hits={units.format_number(self.hits)}, bytes={units.format_bytes(self.bytes)})"

class Cluster:
    def __init__(self, id: str, secret: str):
        self.id = id
        self.secret = secret
        self.token: Optional[Token] = None
        self.fetch_time: float = 0
        self.token_ttl: float = 0
        self.token_scheduler: Optional[int] = None
        self.socket_io = ClusterSocketIO(self)
        self.want_enable: bool = False
        self.enabled = True
        self.keepalive_task: Optional[int] = None
        self.delay_enable_task: Optional[int] = None
        self.counter = ClusterCounter()

    def __repr__(self):
        return f"Cluster(id={self.id})"

    async def get_token(self):
        if self.token is None or time.time() - self.fetch_time > self.token_ttl - 300:
            await self._fetch_token()

        if self.token is None or self.token.last + self.token.ttl < time.time():
            raise RuntimeError('token expired')
        
        return self.token.token

    async def _fetch_token(self):
        async with aiohttp.ClientSession(
            config.const.base_url
        ) as session:
            logger.tdebug("cluster.debug.fetch_token", cluster=self.id)
            async with session.get(
                f"/openbmclapi-agent/challenge",
                params={
                    "clusterId": self.id
                }
            ) as resp:
                challenge = (await resp.json())['challenge']
                signature = hmac.new(
                    self.secret.encode("utf-8"), digestmod=hashlib.sha256
                )
                signature.update(challenge.encode())
                signature = signature.hexdigest()
            async with session.post(
                "/openbmclapi-agent/token",
                data = {
                    "clusterId": self.id,
                    "challenge": challenge,
                    "signature": signature,
                }
            ) as resp:
                resp.raise_for_status()
                json = await resp.json()
                self.token = Token(time.time(), json['token'], json['ttl'] / 1000.0)
                self.fetch_time = time.monotonic()
                logger.tdebug("cluster.debug.fetch_token_success", cluster=self.id, ttl=units.format_count_datetime(json['ttl'] / 1000.0))
                if self.token_scheduler is not None:
                    scheduler.cancel(self.token_scheduler)
                self.token_scheduler = scheduler.run_later(self.get_token, delay=self.token.ttl - 300)

    async def start_job(self):
        await self.socket_io.connect()

    async def request_cert(self):
        ssl_dir = Path(config.const.ssl_dir)
        if not ssl_dir.exists():
            ssl_dir.mkdir(parents=True, exist_ok=True)
        cert_file, key_file = ssl_dir / f"{self.id}_cert.pem", ssl_dir / f"{self.id}_key.pem"
        result = await self.socket_io.emit(
            "request-cert",
        )
        if result.err is not None:
            logger.terror("cluster.error.socketio.request_cert", cluster=self.id, err=result.err)
            return
        with open(cert_file, "w") as cert, open(key_file, "w") as key:
            cert.write(result.ack["cert"])
            key.write(result.ack["key"])

    async def enable(self):
        cert = await clusters.get_certificate()
        scheduler.cancel(self.delay_enable_task)
        if self.want_enable:
            return
        self.want_enable = True
        logger.tinfo("cluster.info.want_enable", cluster=self.id)
        result = await self.socket_io.emit(
            "enable", {
                "host": cert.host,
                "port": config.const.public_port,
                "byoc": True,
                "version": API_VERSION,
                "noFastEnable": False,
                "flavor": {
                    "storage": "local",
                    "runtime": "python"
                }
            }
        )
        self.want_enable = False
        if result.err:
            self.socketio_error("enable", result)
            return
        self.enabled = True
        scheduler.cancel(self.keepalive_task)
        self.keepalive_task = scheduler.run_repeat_later(self.keepalive, 1, interval=60)

    def hit(self, bytes: int):
        self.counter.hits += 1
        self.counter.bytes += bytes


    async def keepalive(self):
        commit_counter = self.counter.clone()
        result = await self.socket_io.emit(
            "keep-alive", {
                "time": int(time.time() * 1000),
                **asdict(commit_counter)
            }
        )
        if result.err:
            logger.twarning("cluster.warning.kicked_by_remote")
            await self.disable()
            return
        self.counter -= commit_counter
        logger.debug(result.ack)
        timestamp = utils.parse_isotime_to_timestamp(result.ack)
        ping = (time.time() - timestamp) // 0.0002
        logger.tsuccess("cluster.success.keepalive", cluster=self.id, hits=units.format_number(commit_counter.hits), bytes=units.format_bytes(commit_counter.bytes), ping=ping)
        
    async def disable(self, exit: bool = False):
        scheduler.cancel(self.keepalive_task)
        scheduler.cancel(self.delay_enable_task)
        if self.enabled or self.want_enable:
            result = await self.socket_io.emit(
                "disable"
            )
            if result.err:
                self.socketio_error(
                    "disable",
                    result
                )
            logger.tsuccess("cluster.success.cluster.disable", cluster=self.id)
        if not exit:
            self.delay_enable_task = scheduler.run_later(self.enable, 60)
            logger.tinfo("cluster.info.cluster.retry_enable", delay=60)
            

    @property
    def certificate(self):
        return ClusterCertificate(
            f"{self.id}.openbmclapi.933.moe",
            Path(config.const.ssl_dir) / f"{self.id}_cert.pem", 
            Path(config.const.ssl_dir) / f"{self.id}_key.pem"
        )

    def socketio_error(self, type: str, result: 'SocketIOEmitResult'):
        err = result.err
        if "message" in err:
            logger.terror("cluster.error.socketio", type=type, id=self.id, err=err["message"])
        else:
            logger.terror("cluster.error.socketio", type=type, id=self.id, err=err)

class ClusterSocketIO:
    def __init__(self, cluster: Cluster) -> None:
        self.cluster = cluster
        self.sio = socketio.AsyncClient(
            logger=True,
            handle_sigint=False
        )
    
    async def connect(self):
        auth = {
            "token": await self.cluster.get_token()
        }

        self.setup_handlers()

        await self.sio.connect(
            config.const.base_url,
            transports=["websocket"],
            auth=auth
        )

    def setup_handlers(self):
        @self.sio.on("connect") # type: ignore
        async def _() -> None:
            logger.tdebug("cluster.debug.socketio.connected", cluster=self.cluster.id)

        @self.sio.on("disconnect") # type: ignore
        async def _() -> None:
            logger.tdebug("cluster.debug.socketio.disconnected", cluster=self.cluster.id)

        @self.sio.on("message") # type: ignore
        async def _(message: Any):
            if isinstance(message, dict) and "message" in message:
                message = message["message"]
            logger.tinfo("cluster.info.socketio.message", cluster=self.cluster.id, message=message)

    async def disconnect(self):
        await self.sio.disconnect()

    async def _check_connect(self):
        if not self.sio.connected:
            await self.connect()

    async def emit(self, event: str, data: Any = {}, timeout: Optional[float] = None) -> 'SocketIOEmitResult':
        await self._check_connect()
        fut = asyncio.get_event_loop().create_future()

        async def callback(data: tuple[Any, Any]):
            fut.set_result(SocketIOEmitResult(data[0], data[1] if len(data) > 1 else None))
        await self.sio.emit(
            event, data, callback=callback
        )
        if timeout is not None:
            scheduler.run_later(lambda: fut.set_exception(asyncio.TimeoutError), timeout)
        try:
            await fut
        except:
            raise
        return fut.result()

@dataclass
class ClusterCertificate:
    host: str
    cert: Path
    key: Path

    @property
    def is_valid(self):
        return self.host and self.cert.exists() and self.key.exists()

@dataclass
class SocketIOEmitResult:
    err: Any
    ack: Any

class StorageFile(metaclass=abc.ABCMeta):
    type: str = "abstract"
    def __init__(self, hash: str, size: int, mtime: float) -> None:
        self.hash = hash
        self.size = size
        self.mtime = int(mtime * 1000)

class LocalStorageFile(StorageFile):
    type: str = "local"
    def __init__(self, hash: str, size: int, mtime: float, path: Path) -> None:
        super().__init__(hash=hash, size=size, mtime=mtime)
        self.path = path

class URLStorageFile(StorageFile):
    type: str = "url"
    def __init__(self, hash: str, size: int, mtime: float, url: str) -> None:
        super().__init__(hash=hash, size=size, mtime=mtime)
        self.url = url

class MemoryStorageFile(StorageFile):
    type: str = "memory"
    def __init__(self, hash: str, size: int, mtime: float, data: bytes) -> None:
        super().__init__(hash=hash, size=size, mtime=mtime)
        self.data = data

ROOT = Path(__file__).parent.parent

API_VERSION = "1.11.0"
USER_AGENT = f"openbmclapi/{API_VERSION} python-openbmclapi/3.0"
CHECK_FILE_CONTENT = "Python OpenBMCLAPI"
CHECK_FILE_MD5 = hashlib.md5(CHECK_FILE_CONTENT.encode("utf-8")).hexdigest()
CHECK_FILE = File(
    CHECK_FILE_MD5,
    CHECK_FILE_MD5,
    len(CHECK_FILE_CONTENT),
    946684800000

)

def convert_file_to_storage_file(file: File) -> SFile:
    return SFile(
        file.path,
        file.size,
        file.mtime / 1000.0,
        file.hash
    )
clusters = ClusterManager()

async def init():
    # read clusters from config
    config_clusters = config.Config.get("clusters")
    for ccluster in config_clusters:
        cluster = Cluster(
            ccluster['id'],
            ccluster['secret'],
        )
        if not cluster.id:
            continue
        logger.tsuccess("cluster.success.load_cluster", id=cluster.id)
        clusters.add_cluster(cluster)
    if len(clusters.clusters) == 0:
        logger.terror("cluster.error.no_cluster")
        utils.pause()
        return
    config_storages = config_clusters = config.Config.get("storages")
    for cstorage in config_storages:
        type = cstorage['type']
        if type == "local":
            storage = storages.LocalStorage(cstorage['path'], cstorage['width'])
        elif type == "alist":
            storage = storages.AlistStorage(cstorage['path'], cstorage['width'], cstorage['url'], cstorage['username'], cstorage['password'])
        else:
            logger.terror("cluster.error.unspported_storage", type=type, path=cstorage['path'])
            continue
        clusters.storage_manager.add_storage(storage)

    scheduler.run_later(
        clusters.start, 0
    )

async def unload():
    await clusters.stop()

def check_sign(hash: str, s: str, e: str):
    if not config.const.check_sign:
        return True
    return any(
        utils.check_sign(hash, cluster.secret, s, e) for cluster in clusters.clusters
    )

def get_cluster_id_from_sign(hash: str, s: str, e: str) -> Optional[str]:
    for cluster in clusters.clusters:
        if utils.check_sign(hash, cluster.secret, s, e):
            return cluster.id
    return None


routes = web.routes
aweb = web.web

@routes.get("/measure/{size}")
async def _(request: aweb.Request):
    try:
        size = int(request.match_info["size"])
        query = request.query
        s = query.get("s", "")
        e = query.get("e", "")
        if not check_sign(f"/measure/{size}", s, e):
            return aweb.Response(status=403)
        cluster_id = get_cluster_id_from_sign(f"/measure/{size}", s, e)
        """response = aweb.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Length": str(size * 1024 * 1024),
                "Content-Type": "application/octet-stream",
            },
        )
        await response.prepare(request)
        for _ in range(size):
            await response.write(b'\x00' * 1024 * 1024)
        await response.write_eof()
        return response"""
        return aweb.HTTPFound(
            f"https://speedtest1.online.sh.cn:8080/download?size={size * 1024 * 1024}&r=0.7129844570865569"
        )
    except:
        return aweb.Response(status=400)
    
@routes.get("/download/{hash}")
async def _(request: aweb.Request):
    try:
        hash = request.match_info["hash"]
        query = request.query
        s = query.get("s", "")
        e = query.get("e", "")
        if not check_sign(request.match_info["hash"], s, e):
            return aweb.Response(status=403)
        cluster_id = get_cluster_id_from_sign(hash, s, e)

        # get cluster instance
        resp = aweb.Response(status=403)
        cluster = clusters.get_cluster_by_id(cluster_id)
        if cluster is None:
            return resp

        file = await clusters.storage_manager.get_file(hash)
        start = request.http_range.start or 0
        end = request.http_range.stop or file.size
        size = end - start + 1

        cluster.hit(size)
        # add database
        # stats
        if isinstance(file, LocalStorageFile):
            resp = aweb.FileResponse(
                file.path
            )
        elif isinstance(file, MemoryStorageFile):
            resp = aweb.Response(
                body=file.data
            )
        elif isinstance(file, URLStorageFile):
            resp= aweb.HTTPFound(
                file.url
            )
        return resp
    except:
        return aweb.Response(status=400)