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

from . import utils, logger, config, scheduler, units, storages, i18n
from .storages import File as SFile

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

    async def get_missing_files(self, files: set[File]):
        function = None
        if function is None:
            logger.twarning("cluster.warning.no_check_function")
            function = self._check_exists
        with tqdm(
            total=len(files) * len(self.available_storages),
            desc="Checking files",
            unit="file",
            unit_scale=True,
        ) as pbar:
            missing_files = set().union(await asyncio.gather(*(self._get_missing_file(function, file, pbar) for file in files)))
            if None in missing_files:
                missing_files.remove(None)
            return missing_files or set()
        
    
    async def _get_missing_file(self, function: Callable[..., Coroutine[Any, Any, bool]], file: File, pbar: tqdm):
        if all(await asyncio.gather(*(self._get_missing_file_storage(function, file, storage, pbar) for storage in self.available_storages))):
            return None
        return file
    
    async def _get_missing_file_storage(self, function: Callable[..., Coroutine[Any, Any, bool]], file: File, storage: storages.iStorage, pbar: tqdm):
        result = await function(file, storage)
        pbar.update(1)
        return result
    
    async def _check_exists(self, file: File, storage: storages.iStorage):
        return await storage.exists(file.hash)
    async def _check_size(self, file: File, storage: storages.iStorage):
        return await self._check_exists(file, storage) and await storage.get_size(file.hash) == file.size
    async def _check_hash(self, file: File, storage: storages.iStorage):
        return await self._check_exists(file, storage) and utils.equals_hash(file.hash, await storage.read_file(file.hash))

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
        self.sync_sem: utils.SemaphoreLock = utils.SemaphoreLock(10)
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

        await self.clusters.storage_manager.available()
        configurations: defaultdict[str, deque[OpenBMCLAPIConfiguration]] = defaultdict(deque)
        for configuration in await asyncio.gather(*(asyncio.create_task(self._get_configuration(cluster)) for cluster in self.clusters.clusters)):
            for k, v in configuration.items():
                configurations[k].append(v)
        # get better configuration
        configuration = max(configurations.items(), key=lambda x: x[1][0].concurrency)[1][0]
        logger.tinfo("cluster.info.sync_configuration", source=configuration.source, concurrency=configuration.concurrency)
        self.sync_sem.set_value(configuration.concurrency)

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
        hash = msg[0] if len(msg) > 0 else None
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
        self.clusters: list['Cluster'] = []
        self.file_manager = FileListManager(self)
        self.storage_manager = StorageManager(self)

    def add_cluster(self, cluster: 'Cluster'):
        self.clusters.append(cluster)

    async def start(self):
        self.storage_manager.init()
        logger.tdebug("cluster.debug.base_url", base_url=config.const.base_url)
        # check files
        await self.file_manager.sync()



class Cluster:
    def __init__(self, id: str, secret: str, port: int, public_port: int = -1, host: str = "", byoc: bool = False, cert: Optional[str] = None, key: Optional[str] = None):
        self.id = id
        self.secret = secret
        self.port = port
        self.public_port = public_port
        self.host = host
        self.byoc = byoc
        self.cert = cert
        self.key = key
        self.token: Optional[Token] = None
        self.last_token: float = 0
        self.token_ttl: float = 0
        self.token_scheduler: Optional[int] = None

    def __repr__(self):
        return f"Cluster(id={self.id}, host={self.host}, port={self.port}, public_port={self.public_port}, byoc={self.byoc}, cert={self.cert}, key={self.key})"

    async def get_token(self):
        if self.token is None or time.time() - self.last_token > self.token_ttl - 300:
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
            ccluster['port'],
            ccluster['public_port'],
            ccluster['host'],
            ccluster['byoc'],
            ccluster['cert'],
            ccluster['key']
        )
        if not cluster.id:
            continue
        logger.tsuccess("cluster.success.load_cluster", id=cluster.id, host=cluster.host, port=cluster.port)
        clusters.add_cluster(cluster)
    
    config_storages = config_clusters = config.Config.get("storages")
    for cstorage in config_storages:
        type = cstorage['type']
        if type == "local":
            storage = storages.LocalStorage(cstorage['path'])
        elif type == "alist":
            storage = storages.AlistStorage(cstorage['path'], cstorage['url'], cstorage['username'], cstorage['password'])
        else:
            logger.terror("cluster.error.unspported_storage", type=type, path=cstorage['path'])
            continue
        clusters.storage_manager.add_storage(storage)

    scheduler.run_later(
        clusters.start, 0
    )