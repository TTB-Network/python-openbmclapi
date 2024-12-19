import abc
import asyncio
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
import datetime
import hashlib
import hmac
import io
import json
from pathlib import Path
import time
from typing import Any, Callable, Coroutine, Optional
import aiohttp.client_exceptions
import pyzstd as zstd
import aiohttp
from tqdm import tqdm

from . import web
from . import utils, logger, config, scheduler, units, storages, i18n
from .storages import File as SFile, MeasureFile
import socketio
import urllib.parse as urlparse
from . import database as db
from .config import USER_AGENT, API_VERSION
from .utils import WrapperTQDM

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID

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

@dataclass
class FailedFile:
    file: File
    failed_times: int
    first_time: datetime.datetime
    last_failed_time: float

    def __hash__(self) -> int:
        return hash(self.file)
    

class StorageManager:
    def __init__(self, clusters: 'ClusterManager'):
        self.clusters = clusters
        self.storages: deque[storages.iStorage] = deque()
        self.available_storages: deque[storages.iStorage] = deque()
        self.check_available: utils.CountLock = utils.CountLock()

        self.check_available.acquire()

        self.check_type_file = config.const.check_type
        self.cache_filelist: defaultdict[storages.iStorage, defaultdict[str, storages.File]] = defaultdict(defaultdict) # type: ignore

        self.retries = 3

    def init(self):
        scheduler.run_repeat_later(self._check_available, 1, 120)

    async def _check_available(self):
        for storage in self.storages:
            res = False
            try:
                res = await asyncio.wait_for(self.__check_available(storage), 10)
            except asyncio.TimeoutError:
                if storage in self.available_storages:
                    self.available_storages.remove(storage)
            except:
                logger.ttraceback("storage.error.check_available", type=storage.type, path=storage.path, url=getattr(storage, "url", None))
                if storage in self.available_storages:
                    self.available_storages.remove(storage)
            if res:
                if storage not in self.available_storages:
                    self.available_storages.append(storage)
            elif storage in self.available_storages:
                self.available_storages.remove(storage)
        logger.debug(f"Available storages: {len(self.available_storages)}")
        if len(self.available_storages) > 0:
            self.check_available.release()
        else:
            self.check_available.acquire()
        
    async def __check_available(self, storage: storages.iStorage):
        file = MeasureFile(
            0
        )
        if not await storage.exists(file):
            await storage.write_file(
                file,
                io.BytesIO(CHECK_FILE_CONTENT.encode("utf-8")),
            )
        return await storage.get_size(file) == len(CHECK_FILE_CONTENT)

    def add_storage(self, storage: storages.iStorage):
        self.storages.append(storage)

    async def available(self):
        await self.check_available.wait()
        return len(self.available_storages) > 0
    
    async def write_file(self, file: File, content: bytes):
        return all(await asyncio.gather(*(asyncio.create_task(self._write_file(
            file,
            io.BytesIO(content),
            storage
        )) for storage in self.available_storages)))

    async def get_missing_files(self, files: set[File]) -> set[File | Any]:
        function = None
        if self.check_type_file == "exists":
            function = self._check_exists
        elif self.check_type_file == "size":
            function = self._check_size
        elif self.check_type_file == "hash":
            function = self._check_hash
        if function is None:
            logger.twarning("cluster.warning.no_check_function")
            function = self._check_exists

        await self.available()
        with WrapperTQDM(tqdm(
            total=len(self.available_storages) * 256,
            desc="List Files",
            unit="dir",
            unit_scale=True
        )) as pbar:
            await asyncio.gather(*(self.get_storage_filelist(storage, pbar) for storage in self.available_storages))
        with WrapperTQDM(tqdm(
            total=len(files) * len(self.available_storages),
            desc="Checking files",
            unit="file",
            unit_scale=True,
        )) as pbar:
            missing_files = set()
            waiting_files: defaultdict[storages.iStorage, asyncio.Queue[File]] = defaultdict(lambda: asyncio.Queue[File]())
            
            for storage in self.available_storages:
                for file in files:
                    waiting_files[storage].put_nowait(file)
            
            await asyncio.gather(*(self._get_missing_file_storage(function, missing_files, waiting_files[storage], storage, pbar) for storage in self.available_storages))
            
            # clear cache_list
            self.cache_filelist.clear()
            return missing_files
    
    async def get_storage_filelist(self, storage: storages.iStorage, pbar: WrapperTQDM):
        result = await storage.list_files(pbar)
        for file in result:
            self.cache_filelist[storage][file.hash] = file
        return result

    async def _get_missing_file_storage(self, function: Callable[..., Coroutine[Any, Any, bool]], missing_files: set[File], files: asyncio.Queue[File], storage: storages.iStorage, pbar: WrapperTQDM):
        while not files.empty():
            file = await files.get()
            if await function(file, storage):
                pbar.update(1)
            else:
                missing_files.add(file)
            files.task_done()
            await asyncio.sleep(0)
    
    async def _check_exists(self, file: File, storage: storages.iStorage):
        if storage in self.cache_filelist:
            file_hash = file.hash
            return file_hash in self.cache_filelist[storage]
        return await storage.exists(convert_file_to_storage_file(file))
    async def _check_size(self, file: File, storage: storages.iStorage):
        if storage in self.cache_filelist:
            file_hash = file.hash
            return file_hash in self.cache_filelist[storage] and self.cache_filelist[storage][file_hash].size == file.size
        return await self._check_exists(file, storage) and await storage.get_size(convert_file_to_storage_file(file)) == file.size
    async def _check_hash(self, file: File, storage: storages.iStorage):
        return await self._check_exists(file, storage) and utils.equals_hash(file.hash, (await storage.read_file(convert_file_to_storage_file(file))).getvalue())

    async def get_file(self, hash: str, use_master: bool = False):
        file = None
        storage_file = SFile(
            hash,
            0,
            0,
            hash
        )
        if await self.available() and not use_master:
            storage = self.get_width_storage()
            print(storage)
            if isinstance(storage, storages.LocalStorage) and await storage.exists(storage_file):
                file = LocalStorageFile(
                    hash,
                    await storage.get_size(storage_file),
                    await storage.get_mtime(storage_file),
                    storage,
                    Path(str(storage.get_path(storage_file)))
                )
            elif isinstance(storage, storages.AlistStorage):
                file = URLStorageFile(
                    hash,
                    await storage.get_size(storage_file),
                    await storage.get_mtime(storage_file),
                    storage,
                    await storage.get_url(storage_file)
                )
            elif isinstance(storage, storages.WebDavStorage):
                result_file = await storage.get_file(
                    storage_file
                )
                if result_file.data_size() == 0 and result_file.url:
                    file = URLStorageFile(
                        hash,
                        await storage.get_size(storage_file),
                        await storage.get_mtime(storage_file),
                        storage,
                        result_file.url
                    )
                if result_file.data_size() > 0:
                    file = MemoryStorageFile(
                        hash,
                        await storage.get_size(storage_file),
                        await storage.get_mtime(storage_file),
                        result_file.data.getvalue()
                    )
        if isinstance(file, URLStorageFile) and not file.url:
            file = None
        if file is not None:
            return file
        async with aiohttp.ClientSession(
                config.const.base_url,
            ) as session:
            for cluster in self.clusters.clusters:
                async with session.get(
                    f"/openbmclapi/download/{hash}",
                    params={
                        "noopen": str(1)
                    },
                    headers={
                        "User-Agent": USER_AGENT,
                        "Authorization": f"Bearer {await cluster.get_token()}"
                    }
                ) as resp:
                    # check hash, if hash is not mismatch.
                    body = await resp.content.read()
                    utils.raise_service_error(body)
                    got_hash = utils.get_hash_hexdigest(hash, body)
                    file = MemoryStorageFile(
                        hash,
                        resp.content_length or -1,
                        time.time(),
                        body
                    )
                    if got_hash == hash:
                        break
                    logger.terror("cluster.error.download_hash", got_hash=got_hash, hash=hash, content=body.decode("utf-8", "ignore")[:64])  
        return file

    def get_width_storage(self, c_storage: Optional[storages.iStorage] = None) -> storages.iStorage:
        current_storage = self.available_storages[0]
        if current_storage.current_weight < current_storage.weight:
            current_storage.current_weight += 1
            return current_storage
        else:
            current_storage.current_weight = 0
            self.available_storages.remove(current_storage)
            self.available_storages.append(current_storage)
            if c_storage is not None:
                return c_storage
            return self.get_width_storage(c_storage=c_storage or current_storage)

    async def _write_file(self, file: File, content: io.BytesIO, storage: storages.iStorage):
        if await self._check_exists(file, storage) and await self._check_size(file, storage):
            return True
        retries = 0
        while retries < self.retries:
            try:
                if await storage.write_file(convert_file_to_storage_file(file), content):
                    return True
            except:
                retries += 1
        return False

@dataclass
class OpenBMCLAPIConfiguration:
    source: str
    concurrency: int

@dataclass
class FileDownloadInfo:
    urls: set[tuple['URLResponse', ...]]
    failed: int = 0

@dataclass
class URLResponse:
    url: str
    status: int

    def __str__(self):
        return f"{self.status} | {self.url}"
    
    def __hash__(self):
        return hash((self.url, self.status))

class DownloadStatistics:
    def __init__(self, total: int = 0, size: int = 0):
        self.total_size = size
        self.total_files = total
        self.downloaded_files = 0
        self.failed_files = 0
        self.pbar = None
    
    def __enter__(self):
        self.pbar = WrapperTQDM(tqdm(
            total=self.total_size,
            unit="b",
            unit_scale=True,
            unit_divisor=1024,
            desc=i18n.locale.t("cluster.processbar.download_files")
        ))
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
        self.failed_hashs: asyncio.Queue[FailedFile] = asyncio.Queue()
        self.failed_hash_urls: defaultdict[str, FileDownloadInfo] = defaultdict(lambda: FileDownloadInfo(set()))
        self.task = None

    async def _get_filelist(self, cluster: 'Cluster'):
        try:
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
                    body = await resp.read()
                    if utils.is_service_error(body):
                        utils.raise_service_error(body)
                        return []
                    resp.raise_for_status()
                    if resp.status == 204:
                        return []
                    stream = utils.FileStream(zstd.decompress(body))
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
                        mtime = max(filelist, key=lambda f: f.mtime).mtime
                        self.cluster_last_modified[cluster] = max(mtime, self.cluster_last_modified[cluster])
                    return filelist
        except:
            logger.ttraceback("cluster.error.fetch_filelist", cluster=cluster.id)
            return []


    async def fetch_filelist(self) -> set[File]:
        result_filelist = set().union(*await asyncio.gather(*(asyncio.create_task(self._get_filelist(cluster)) for cluster in self.clusters.clusters)))
        logger.tsuccess("cluster.success.fetch_filelist", total=units.format_number(len(result_filelist)), size=units.format_bytes(sum(f.size for f in result_filelist)))
        return result_filelist

    async def sync(self):
        scheduler.cancel(self.task)
        result = await self.fetch_filelist()
        if not result:
            logger.tsuccess("cluster.success.no_missing_files")
            self.run_task()
            return

        missing = await self.clusters.storage_manager.get_missing_files(result)

        if not missing:
            logger.tsuccess("cluster.success.no_missing_files")
            self.run_task()
            return

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
        self.run_task()

    def run_task(self):
        scheduler.cancel(self.task)
        self.task = scheduler.run_later(self.sync, config.const.sync_interval)

    async def download(self, filelist: set[File]):
        total = len(filelist)
        size = sum(f.size for f in filelist)
        file_queues = asyncio.Queue()
        for file in filelist:
            await file_queues.put(file)
        sessions: list[aiohttp.ClientSession] = []
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
                            "Authorization": f"Bearer {await clusters.clusters[0].get_token()}"
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
        while not file_queues.empty() or not self.failed_hashs.empty():
            recved = 0
            try:
                failed_file = None
                if file_queues.empty():
                    failed_file = await self.failed_hashs.get()
                    file = failed_file.file
                    t = max(0, min(failed_file.failed_times * 10, 600) - (time.monotonic() - failed_file.last_failed_time))
                    logger.tdebug("cluster.debug.retry_download", start_date=failed_file.first_time, file_path=file.path, file_hash=file.hash, file_size=units.format_bytes(file.size), time=units.format_count_time(t * 1e9), count=failed_file.failed_times)
                    await asyncio.sleep(t)
                else:
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
                failed_file = failed_file or FailedFile(file, 0, datetime.datetime.now(), time.monotonic())
                failed_file.last_failed_time = time.monotonic()
                failed_file.failed_times += 1
                await self.failed_hashs.put(failed_file)
                pbar.update_failed()
                r = None
                if "resp" in locals():
                    r = resp
                await self.report(file, e, r)
                continue

    async def report(self, file: File, error: Exception, resp: Optional[aiohttp.ClientResponse] = None):
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
        elif isinstance(error, FileNotFoundError):
            type = "file"
        else:
            type = "unknown"
            logger.error(repr(error), error)
        responses: list[URLResponse] = []
        host = None
        if resp is not None:
            for r in resp.history:
                responses.append(URLResponse(str(r.real_url), r.status))
            responses.append(URLResponse(str(resp.real_url), resp.status))
            host = resp.host
        hash = msg[0] if len(msg) > 0 and type == "hash" else None
        logger.terror(f"clusters.error.downloading", type=type, error=str(error), file_hash=file.hash, file_size=units.format_bytes(file.size), host=host, file_path=file.path, hash=hash, responses="\n".join(("", *(str(r) for r in responses))))
        self.failed_hash_urls[file.hash].failed += 1
        self.failed_hash_urls[file.hash].urls.add(tuple(responses))
        if self.failed_hash_urls[file.hash].failed < 10:
            return
        logger.terror("cluster.error.download.report", file_path=file.path, file_hash=file.hash, file_size=units.format_bytes(file.size), failed=self.failed_hash_urls[file.hash].failed, urls="\n----------------------------------------------------------------\n".join(("\n".join(("", *(str(r) for r in responses))) for responses in self.failed_hash_urls[file.hash].urls)))
        await self._report(self.failed_hash_urls[file.hash].urls)
        self.failed_hash_urls[file.hash].failed = 0
        self.failed_hash_urls[file.hash].urls = set()
    async def _report(self, urls: set[tuple[URLResponse, ...]]):
        async def _r(urls: tuple[URLResponse, ...]):
            async with session.post(
                "/openbmclapi/report", json={
                    "urls": [url.url for url in urls],
                    "error": "Network error",
                }
            ) as resp:
                utils.raise_service_error(await resp.read())
        async with aiohttp.ClientSession(
            config.const.base_url,
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {await clusters.clusters[0].get_token()}"
            }
        ) as session:
            await asyncio.gather(*[_r(urls) for urls in urls])


    async def _get_configuration(self, cluster: 'Cluster'):
        try:
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
                    body = await resp.json()
                    if utils.raise_service_error(body):
                        return {}
                    resp.raise_for_status()
                    return {
                        k: OpenBMCLAPIConfiguration(**v) for k, v in (body).items()
                    }
        except:
            logger.ttraceback("cluster.error.configuration", cluster=cluster.id)
            return {}

class ClusterManager:
    def __init__(self):
        self.cluster_id_tables: dict[str, 'Cluster'] = {}
        self.file_manager = FileListManager(self)
        self.storage_manager = StorageManager(self)
        self.clusters_certificate: dict[str, ClusterCertificate] = {}

    def add_cluster(self, cluster: 'Cluster'):
        self.cluster_id_tables[cluster.id] = cluster

    @property
    def clusters(self):
        return list(self.cluster_id_tables.values())

    async def start(self):
        self.storage_manager.init()
        logger.tdebug("cluster.debug.base_url", base_url=config.const.base_url)

        certificates = await self.get_certificates()
        for cert in certificates:
            await web.start_private_server(
                cert.cert, cert.key
            )
        # start web ssl
        public_port = config.const.public_port
        public_host = cert.host

        logger.tdebug("cluster.debug.public_host", host=public_host, port=public_port, domain=cert.domain)

        # check files
        await self.file_manager.sync()

        # start job

        for cluster in self.clusters:
            await cluster.enable()

    def get_cluster_by_id(self, id: Optional[str] = None) -> Optional['Cluster']:
        return self.cluster_id_tables.get(id or "", None)

    def byoc(self):
        return self.main_certificate is not None

    @property
    def main_certificate(self):
        if not config.const.ssl_cert or not config.const.ssl_key:
            return None
        main = ClusterCertificate(
            config.const.host,
            Path(config.const.ssl_cert),
            Path(config.const.ssl_key)
        )
        if not main.is_valid:
            return None
        return main
        


    async def get_certificates(self, cluster_id: Optional[str] = None):
        if config.const.ssl_cert and config.const.ssl_key:
            main = ClusterCertificate(
                config.const.host,
                Path(config.const.ssl_cert),
                Path(config.const.ssl_key)
            )
            if main.is_valid:
                return [
                    main
                ]
        if not self.clusters_certificate:
            await asyncio.gather(*[cluster.request_cert() for cluster in self.clusters])
            for cluster in self.clusters:
                self.clusters_certificate[cluster.id] = cluster.certificate
        if cluster_id is None:
            return list(self.clusters_certificate.values())
        if cluster_id in self.clusters_certificate:
            return [self.clusters_certificate[cluster_id]]
        return []
    
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
        self.token_scheduler: Optional[int] = None
        self.socket_io = ClusterSocketIO(self)
        self.want_enable: bool = False
        self.enabled = False
        self.enable_count: int = 0
        self.keepalive_task: Optional[int] = None
        self.delay_enable_task: Optional[int] = None
        self.counter: defaultdict[storages.iStorage, ClusterCounter] = defaultdict(ClusterCounter)
        self.no_storage_counter = ClusterCounter()

    def __repr__(self):
        return f"Cluster(id={self.id})"

    async def get_token(self):
        if self.token is None or time.time() - self.token.last > self.token.ttl - 300:
            await self._fetch_token()

        if self.token is None or self.token.last + self.token.ttl < time.time():
            raise RuntimeError('token expired')
        
        return self.token.token

    async def _fetch_token(self):
        async with aiohttp.ClientSession(
            config.const.base_url,
            headers={
                "User-Agent": USER_AGENT
            }
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
                json = {
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

    async def request_cert(self):
        ssl_dir = Path(config.const.ssl_dir)
        if not ssl_dir.exists():
            ssl_dir.mkdir(parents=True, exist_ok=True)
        cert_file, key_file = ssl_dir / f"{self.id}_cert.pem", ssl_dir / f"{self.id}_key.pem"
        logger.tinfo("cluster.info.request_certing", cluster=self.id)
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
        cert = await clusters.get_certificates(self.id)
        scheduler.cancel(self.delay_enable_task)
        if self.want_enable:
            return
        self.want_enable = True
        self.enable_count += 1
        logger.tinfo("cluster.info.want_enable", cluster=self.id)
        try:
            result = await self.socket_io.emit(
                "enable", {
                    "host": config.const.host,
                    "port": config.const.public_port or config.const.port,
                    "byoc": clusters.byoc(),
                    "version": API_VERSION,
                    "noFastEnable": True,
                    "flavor": {
                        "storage": "local",
                        "runtime": f"python/{config.PYTHON_VERSION}"
                    }
                }
            , 120)
        except:
            return
        finally:
            self.want_enable = False
        if result.err:
            self.socketio_error("enable", result)
            self.retry()
            return
        self.enabled = True
        self.enable_count = 0
        scheduler.cancel(self.keepalive_task)
        self.keepalive_task = scheduler.run_repeat_later(self.keepalive, 1, interval=60)
        logger.tsuccess("cluster.success.enabled", cluster=self.id)

    def hit(self, storage: Optional[storages.iStorage], bytes: int):
        if storage is None:
            self.no_storage_counter.hits += 1
            self.no_storage_counter.bytes += bytes
            return
        self.counter[storage].hits += 1
        self.counter[storage].bytes += bytes

    async def keepalive(self):
        commit_no_storage_counter = self.no_storage_counter.clone()
        commit_counter = {
            storage: counter.clone() for storage, counter in self.counter.items()
        }
        total_counter = ClusterCounter()
        for counter in (
            commit_no_storage_counter,
            *commit_counter.values()
        ):
            total_counter.hits += counter.hits
            total_counter.bytes += counter.bytes
        result = await self.socket_io.emit(
            "keep-alive", {
                "time": int(time.time() * 1000),
                **asdict(total_counter)
            }
        )
        if result.err or not result.ack:
            logger.twarning("cluster.warning.kicked_by_remote")
            await self.disable()
            return
        self.no_storage_counter -= commit_no_storage_counter
        for storage, counter in commit_counter.items():
            self.counter[storage] -= counter
        timestamp = result.ack / 1000.0 if isinstance(result.ack, int) else utils.parse_isotime_to_timestamp(result.ack)
        ping = (time.time() - timestamp) // 0.0002
        logger.tsuccess("cluster.success.keepalive", cluster=self.id, hits=units.format_number(total_counter.hits), bytes=units.format_bytes(total_counter.bytes), ping=ping)

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
        self.want_enable = False
        self.enabled = False
        if not exit:
            self.retry()

    def retry(self):
        delay = ((self.enable_count  + 1) ** 2) * 60
        self.delay_enable_task = scheduler.run_later(self.enable, delay)
        logger.tinfo("cluster.info.cluster.retry_enable", cluster=self.id, delay=units.format_count_datetime(delay))
            

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
            logger.terror("cluster.error.socketio", type=type, cluster=self.id, err=err["message"])
        else:
            logger.terror("cluster.error.socketio", type=type, cluster=self.id, err=err)

class ClusterSocketIO:
    def __init__(self, cluster: Cluster) -> None:
        self.cluster = cluster
        self.sio = socketio.AsyncClient(
            logger=config.const.debug,
            handle_sigint=False,
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

        @self.sio.on("exception") # type: ignore
        async def _(message: Any):
            if isinstance(message, dict) and "message" in message:
                message = message["message"]
            logger.terror("cluster.error.socketio.message", cluster=self.cluster.id, message=message)

        @self.sio.on("warden-error") # type: ignore
        async def _(message: Any):
            with open(f"{logger.dir}/warden-error.log", "a") as f:
                f.write(json.dumps({
                    "time": datetime.datetime.now().isoformat(),
                    "cluster": self.cluster.id,
                    "message": message,
                }) + "\n")
            if isinstance(message, dict) and "message" in message:
                message = message["message"]
            logger.terror("cluster.error.socketio.warden", cluster=self.cluster.id, message=message)


    async def disconnect(self):
        await self.sio.disconnect()

    async def _check_connect(self):
        if not self.sio.connected:
            await self.connect()

    async def emit(self, event: str, data: Any = None, timeout: Optional[float] = None) -> 'SocketIOEmitResult':
        await self._check_connect()
        fut = asyncio.get_event_loop().create_future()

        async def callback(data: tuple[Any, Any]):
            fut.set_result(SocketIOEmitResult(data[0], data[1] if len(data) > 1 else None))
        await self.sio.emit(
            event, data, callback=callback
        )
        timeout_task = None
        if timeout is not None:
            timeout_task = scheduler.run_later(lambda: not fut.done() and fut.set_exception(asyncio.TimeoutError), timeout)
        try:
            await fut
        except:
            raise
        scheduler.cancel(timeout_task)
        return fut.result()  

@dataclass
class ClusterCertificate:
    host: str
    cert: Path
    key: Path

    @property
    def is_valid(self):
        return self.host and self.cert.exists() and self.key.exists()
    
    @property
    def domain(self):
        domains = self.domains
        domains.sort(key=lambda x: x.count("*"))
        return domains[0] if domains else self.host

    @property
    def domains(self):
        try:
            cert = x509.load_pem_x509_certificate(self.cert.read_bytes(), default_backend())
            domains = []
            for subject in cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME):
                if isinstance(subject.value, str):
                    domains.append(subject.value)
                elif isinstance(subject.value, bytes):
                    domains.append(subject.value.decode("utf-8"))
            return domains
        except:
            return []

@dataclass
class SocketIOEmitResult:
    err: Any
    ack: Any

class StorageFile(metaclass=abc.ABCMeta):
    type: str = "abstract"
    def __init__(self, hash: str, size: int, mtime: float, storage: Optional[storages.iStorage]) -> None:
        self.hash = hash
        self.size = size
        self.mtime = int(mtime * 1000)
        self.storage = storage

class LocalStorageFile(StorageFile):
    type: str = "local"
    def __init__(self, hash: str, size: int, mtime: float, storage: storages.iStorage, path: Path) -> None:
        super().__init__(hash=hash, size=size, mtime=mtime, storage=storage)
        self.path = path

class URLStorageFile(StorageFile):
    type: str = "url"
    def __init__(self, hash: str, size: int, mtime: float, storage: storages.iStorage, url: str) -> None:
        super().__init__(hash=hash, size=size, mtime=mtime, storage=storage)
        self.url = url

class MemoryStorageFile(StorageFile):
    type: str = "memory"
    def __init__(self, hash: str, size: int, mtime: float, data: bytes, storage: Optional[storages.iStorage] = None) -> None:
        super().__init__(hash=hash, size=size, mtime=mtime, storage=storage)
        self.data = data

ROOT = Path(__file__).parent.parent

CHECK_FILE_CONTENT = "Python OpenBMCLAPI"
CHECK_FILE_MD5 = hashlib.md5(CHECK_FILE_CONTENT.encode("utf-8")).hexdigest()
CHECK_FILE = File(
    CHECK_FILE_MD5,
    CHECK_FILE_MD5,
    len(CHECK_FILE_CONTENT),
    946684800000

)
MEASURES_HASH: dict[int, str] = {
}
MEASURE_BUFFER: bytes = b'\x00'

routes = web.routes
aweb = web.web
clusters = ClusterManager()

def convert_file_to_storage_file(file: File) -> SFile:
    return SFile(
        file.path,
        file.size,
        file.mtime / 1000.0,
        file.hash
    )

def init_measure_block(size: int):
    MEASURES_HASH[size] = hashlib.md5(MEASURE_BUFFER * 1024 * 1024 * size).hexdigest()

async def init_measure(maxsize: int = 50):
    for i in range(1, maxsize, 10):
        init_measure_block(i)

async def init_measure_file(
    storage: storages.iStorage,
    size: int,
    hash: str
):
    storage_file = MeasureFile(
        size,
    )
    try:
        if await storage.exists(storage_file) and await storage.get_size(storage_file) == size * 1024 * 1024:
            return True
        await storage.write_file(
            storage_file,
            io.BytesIO(
                MEASURE_BUFFER * 1024 * 1024 * size
            )
        )
        return True
    except:
        logger.ttraceback("cluster.error.init_measure_file", path=storage.path, type=storage.type, size=units.format_bytes(size * 1024 * 1024), hash=hash)
    return False
async def init_measure_files():
    results = await asyncio.gather(*[init_measure_file(storage, size, MEASURES_HASH[size]) for storage in clusters.storage_manager.storages for size in MEASURES_HASH])
    logger.debug(results)

async def init():
    logger.tinfo("cluster.info.init", openbmclapi_version=API_VERSION, version=config.VERSION)
    # read clusters from config
    config_clusters = config.Config.get("clusters")
    for ccluster in config_clusters:
        cluster = Cluster(
            ccluster['id'],
            ccluster['secret'],
        )
        if not cluster.id:
            continue
        logger.tsuccess("cluster.success.load_cluster", cluster=cluster.id)
        clusters.add_cluster(cluster)
    if len(clusters.clusters) == 0:
        logger.terror("cluster.error.no_cluster")
        utils.pause()
        return
    config_storages = config_clusters = config.Config.get("storages")
    for cstorage in config_storages:
        storage = storages.init_storage(cstorage)
        if not storage:
            continue
        clusters.storage_manager.add_storage(storage)
    if config.const.measure_storage:
        logger.tinfo("cluster.info.enable.measure_storage")


    db.init_storages_key(*clusters.storage_manager.storages)

    scheduler.run_later(
        clusters.start, 0
    )

async def unload():
    for storage in clusters.storage_manager.storages:
        if isinstance(storage, storages.AlistStorage):
            await storage.close()
    await clusters.stop()

def check_sign(hash: str, s: str, e: str):
    if not config.const.check_sign:
        return True
    return any(
        utils.check_sign(hash, cluster.secret, s, e) for cluster in clusters.clusters
    )

def get_cluster_id_from_sign(hash: str, s: str, e: str) -> Optional[str]:
    for cluster in clusters.clusters:
        if utils.check_sign_without_time(hash, cluster.secret, s, e):
            return cluster.id
    return None

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
        file = MeasureFile(
            size
        )
        if config.const.measure_storage:
            init_measure_block(size)
            await init_measure_files()
            storage = clusters.storage_manager.storages[0]
            if isinstance(storage, storages.AlistStorage):
                url = await storage.get_url(file)
                logger.debug("Requested measure url:", url)
                if url:
                    return aweb.HTTPFound(url)
            elif isinstance(storage, storages.LocalStorage):
                return aweb.FileResponse(
                    Path(str(storage.get_path(file)))
                )
            elif isinstance(storage, storages.WebDavStorage):
                file = await storage.get_file(file)
                if file.url:
                    logger.debug("Requested measure url:", file.url)
                    return aweb.HTTPFound(file.url)
                elif file.size >= 0:
                    return aweb.Response(
                        status=200,
                        headers={
                            "Content-Length": str(file.size),
                            "Content-Type": "application/octet-stream",
                        },
                        body=file.data
                    )

        if config.const.measure_storage:
            logger.twarning("cluster.warning.measure_storage")
        response = aweb.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Length": str(size * 1024 * 1024),
                "Content-Type": "application/octet-stream",
            },
        )
        await response.prepare(request)
        for _ in range(size):
            await response.write(MEASURE_BUFFER * 1024 * 1024)
        await response.write_eof()
        return response
    

        """return aweb.HTTPFound(
            f"https://speedtest1.online.sh.cn:8080/download?size={size * 1024 * 1024}&r=0.7129844570865569"
        )"""
    except:
        logger.traceback()
        return aweb.Response(status=400)
    
@routes.get("/download/{hash}")
async def _(request: aweb.Request):
    try:
        hash = request.match_info["hash"]
        query = request.query
        address = request.custom_address # type: ignore
        user_agent = request.headers.get("User-Agent", "")
        s = query.get("s", "")
        e = query.get("e", "")
        if not check_sign(request.match_info["hash"], s, e):
            db.add_response(
                address,
                db.StatusType.FORBIDDEN,
                user_agent
            )
            return aweb.Response(status=403)
        cluster_id = get_cluster_id_from_sign(hash, s, e)

        # get cluster instance
        cluster = clusters.get_cluster_by_id(cluster_id)
        if cluster is None:
            db.add_response(
                address,
                db.StatusType.FORBIDDEN,
                user_agent
            )
            return aweb.Response(status=403)
        try:
            file = await asyncio.wait_for(asyncio.create_task(clusters.storage_manager.get_file(hash)), 5)
        except:
            logger.ttraceback("cluster.error.get_file", hash=hash)
            file = await asyncio.create_task(clusters.storage_manager.get_file(hash, True))
        if file is None:
            db.add_response(
                address,
                db.StatusType.NOT_FOUND,
                user_agent
            )
            return aweb.Response(status=404)
        
        resp = aweb.Response(status=500)
        
        start = request.http_range.start or 0
        end = request.http_range.stop or file.size - 1
        size = end - start + 1

        cluster.hit(file.storage, size)
        # add database
        # stats
        name = query.get("name")
        if name is not None:
            name = urlparse.quote(name)
        headers = {}
        if name:
            headers["Content-Disposition"] = f"attachment; filename={name}"
        headers["X-BMCLAPI-Hash"] = hash

        if isinstance(file, LocalStorageFile):
            resp = aweb.FileResponse(
                file.path,
                headers=headers
            )
        elif isinstance(file, MemoryStorageFile):
            resp = aweb.Response(
                body=file.data[start:end + 1],
                headers={
                    "Content-Range": f"bytes={start}-{end}/{file.size}",
                    "Content-Length": str(size),
                    "Content-Type": "application/octet-stream",
                    **headers
                }
            )
        elif isinstance(file, URLStorageFile):
            resp = aweb.HTTPFound(
                file.url,
                headers=headers
            )
        type = None
        if resp.status == 200:
            type = db.StatusType.SUCCESS
        elif resp.status == 206:
            type = db.StatusType.PARTIAL
        elif resp.status == 403:
            type = db.StatusType.FORBIDDEN
        elif resp.status == 404:
            type = db.StatusType.NOT_FOUND
        elif resp.status == 302:
            type = db.StatusType.REDIRECT
        if (type == db.StatusType.SUCCESS or type is None) and request.http_range.stop is not None:
            type = db.StatusType.PARTIAL
        storage_name = file.storage.unique_id if file.storage is not None else None
        db.add_file(cluster.id, storage_name, size)
        db.add_response(
            address,
            type or db.StatusType.ERROR,
            user_agent
        )
        return resp
    except:
        logger.traceback()
        db.add_response(
            address,
            db.StatusType.ERROR,
            user_agent
        )
        return aweb.Response(status=500)