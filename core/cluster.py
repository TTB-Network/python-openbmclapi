from collections import deque
import datetime
import hmac
from pathlib import Path
import tempfile
import time
from typing import Any, Optional
import aiohttp
import anyio
import anyio.abc
import pyzstd as zstd
import tqdm
import socketio

from core import units

from . import utils
from .abc import BMCLAPIFile, Certificate, CertificateType, OpenBMCLAPIConfiguration, ResponseFile, SocketEmitResult
from .logger import logger
from .config import API_VERSION, ROOT_PATH, cfg, USER_AGENT
from .storage import CheckStorage, StorageManager

class TokenManager:
    def __init__(
        self,
        id: str,
        secret: str,
    ):
        self._id = id
        self._secret = secret
        self._token = None
        self._task_group = None
    

    async def get_token(self):
        if self._token is None:
            await self.fetch_token()
        return self._token
    
    async def fetch_token(self):
        async with aiohttp.ClientSession(
            base_url=cfg.base_url,
            headers={
                "User-Agent": USER_AGENT,
            }
        ) as session:
            
            # challenge
            async with session.get(
                "/openbmclapi-agent/challenge",
                params={
                    "clusterId": self._id
                }
            ) as resp:
                challenge = (await resp.json())['challenge']
            
            signature = hmac.new(
                self._secret.encode('utf-8'),
                challenge.encode('utf-8'),
                'sha256'
            ).hexdigest()

            async with session.post(
                "/openbmclapi-agent/token",
                json={
                    "clusterId": self._id,
                    "challenge": challenge,
                    "signature": signature
                }
            ) as resp:
                data = await resp.json()
                self._token = data['token']
                ttl = data['ttl'] / 1000.0
                self.schedule_refresh_token(ttl)

    def setup(self, task_group: anyio.abc.TaskGroup):
        self._task_group = task_group
        
            # scheduleRefreshToken
    def schedule_refresh_token(self, ttl: float):
        if self._task_group is None:
            raise RuntimeError("Task group is not set")
        self._task_group.start_soon(self._schedule_refresh_token, ttl)

    async def _schedule_refresh_token(self, ttl: float):
        next = max(ttl - 600, ttl / 2)
        logger.tdebug("cluster.refresh_token.schedule", id=self._id, next=next)
        await anyio.sleep(ttl)
        try:
            await self.refresh_token()
        except:
            logger.ttraceback("cluster.refresh_token", id=self._id)

    async def refresh_token(self):
        async with aiohttp.ClientSession(
            base_url=cfg.base_url,
            headers={
                "User-Agent": USER_AGENT,
            }
        ) as session:
            async with session.post(
                "/openbmclapi-agent/token",
                json={
                    "clusterId": self._id,
                    "token": self._token
                }
            ) as resp:
                data = await resp.json()
                self._token = data['token']
                ttl = data['ttl'] / 1000.0
                self.schedule_refresh_token(ttl)

    async def get_socketio_token(self):
        return {
            "token": await self.get_token(),
        }

class ClusterCounter:
    def __init__(
        self,
        hits: int = 0,
        bytes: int = 0
    ):
        self.hits = hits
        self.bytes = bytes

    def clone(self):
        return ClusterCounter(self.hits, self.bytes)

class Cluster:
    def __init__(
        self,
        id: str,
        secret: str
    ):
        self._token = TokenManager(id, secret)
        self._last_modified = 0
        self.sio = socketio.AsyncClient(
            handle_sigint=False
        )
        self._keepalive_lock = utils.CustomLock(locked=True)
        self._storage_wait = utils.CustomLock(locked=True)
        self._enabled = False
        self._want_enable = False
        self._start_serving = False
        self._stop = False
        self.counter = ClusterCounter()
        self._failed_keepalive = 0
        self._retry_times = 0
        self._task_group = None

    @property
    def id(self):
        return self._token._id
    
    def __repr__(self) -> str:
        return f'<Cluster {self.id}>'

    async def setup(
        self,
        task_group: anyio.abc.TaskGroup
    ):
        self._token.setup(task_group)
        self._task_group = task_group
        
        @self.sio.on("warden-error") # type: ignore
        async def _(message: Any):
            logger.twarning("cluster.warden", id=self.id, msg=message)

        @self.sio.on("exception") # type: ignore
        async def _(message: Any):
            logger.terror("cluster.exception", id=self.id, msg=message)

        @self.sio.on("message") # type: ignore
        async def _(message: Any):
            logger.tinfo("cluster.message", id=self.id, msg=message)

        @self.sio.on("connect") # type: ignore
        async def _():
            logger.tdebug("cluster.connected", id=self.id)

        @self.sio.on("disconnect") # type: ignore
        async def _():
            logger.tdebug("cluster.disconnected", id=self.id)

        task_group.start_soon(self.keepalive)

        @utils.event.callback("storage_disable")
        async def _(msg: Any):
            self._storage_wait.acquire()

        @utils.event.callback("storage_enable")
        async def _(msg: Any):
            self._storage_wait.release()

        await self.connect()

    async def keepalive(self):
        while not self._stop:
            await self._keepalive_lock.wait()
            try:
                current_counter = self.counter.clone()
                start_time = time.time()
                res = await self.emit("keep-alive", {
                    "hits": current_counter.hits,
                    "bytes": current_counter.bytes,
                    "time": int(start_time * 1000)
                })
                if res.err is not None or res.ack is None or not isinstance(res.ack, str):
                    self._failed_keepalive += 1
                    if self._failed_keepalive >= 3:
                        logger.terror("cluster.kicked", id=self.id)
                        await self.disable()
                    else:
                        logger.twarning("cluster.keepalive", id=self.id, failed=self._failed_keepalive)
                else:
                    self._failed_keepalive = 0

                    self.counter.hits -= current_counter.hits
                    self.counter.bytes -= current_counter.bytes
                    resp_time = time.time() - datetime.datetime.fromisoformat(res.ack).timestamp()
                    logger.tsuccess("cluster.keepalive", id=self.id, hits=units.format_number(current_counter.hits), bytes=units.format_number(current_counter.bytes), delay=F"{resp_time * 1000:.4f}")
            except:
                logger.debug_traceback()
            await anyio.sleep(60)

    async def request_cert(self):
        logger.tinfo("cluster.request_cert", id=self.id)
        res = await self.emit("request-cert")

        if res.err is not None:
            logger.terror("cluster.request_cert.error", id=self.id, err=res.err)
            return None
        
        dir = Path(cfg.get("cert.dir"))
        dir.mkdir(parents=True, exist_ok=True)

        cert = dir / f"{self.id}.pem"
        key = dir / f"{self.id}.key"

        with open(cert, "w") as c, open(key, "w") as k:
            c.write(res.ack['cert'])
            k.write(res.ack['key'])

        return Certificate(CertificateType.CLUSTER, str(cert), str(key))

    async def connect(self):
        await self.sio.connect(
            cfg.base_url,
            transports=['websocket'],
            headers={
                "User-Agent": USER_AGENT,
            },
            auth=self._token.get_socketio_token
        )
        
    async def emit(self, event: str, data: Any = None, timeout: Optional[int] = None) -> SocketEmitResult:
        err, ack = None, None
        async def callback(data: Any):
            nonlocal err, ack
            if len(data) == 2:
                err, ack = data
            else:
                err, ack = data, None
            fut.set()

        await self.sio.emit(event, data, callback=callback)

        fut = anyio.Event()

        with anyio.fail_after(timeout):
            await fut.wait()

        return SocketEmitResult(err, ack)
        
    async def get_files(self) -> list[BMCLAPIFile]:
        results: list[BMCLAPIFile] = []
        async with aiohttp.ClientSession(
            base_url=cfg.base_url,
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {await self._token.get_token()}",
            }
        ) as session:
            async with session.get(
                "/openbmclapi/files",
                params={
                    "lastModified": int(self._last_modified * 1000)
                }
            ) as resp:
                if resp.status == 204: # no new files
                    #logger.tdebug("cluster.get_files.no_new_files", id=self.id)
                    return results
                reader = utils.AvroParser(zstd.decompress(await resp.read()))
                for _ in range(reader.read_long()):
                    results.append(BMCLAPIFile(
                        reader.read_string(),
                        reader.read_string(),
                        reader.read_long(),
                        reader.read_long() / 1000.0,
                    ))
                self._last_modified = max(results, key=lambda x: x.mtime).mtime
                logger.tdebug("cluster.get_files", id=self.id, count=len(results), size=units.format_bytes(sum([f.size for f in results])), last_modified=units.format_datetime_from_timestamp(self._last_modified))
        return results

    async def get_configuration(self) -> OpenBMCLAPIConfiguration:
        async with aiohttp.ClientSession(
            base_url=cfg.base_url,
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {await self._token.get_token()}",
            }
        ) as session:
            async with session.get(
                "/openbmclapi/configuration",
            ) as resp:
                return OpenBMCLAPIConfiguration(**(await resp.json())['sync'])

    async def get_token(self):
        return await self._token.get_token()

    # serve

    async def start_serve(self):
        self._start_serving = True
        await self.enable()

    async def enable(self):
        if not self._start_serving or self._stop:
            return
        await self._storage_wait.wait()
        if not self.sio.connected:
            return
        if self._want_enable or self._enabled:
            logger.debug("cluster want enable again")
            return
        self._want_enable = True
        logger.tinfo("cluster.want_enable", id=self.id)
        try:
            res = await self.emit("enable", {
                "host": cfg.host,
                "port": cfg.web_public_port,
                "version": API_VERSION,
                "noFastEnable": False,
                "byoc": utils.get_certificate_type() != CertificateType.CLUSTER,
                "flavor": {
                    "runtime": "python",
                    "storage": "local"
                }
            }, 300)
            if res.err is not None:
                logger.terror("cluster.enable", id=self.id, err=res.err)
                return
            
            self._enabled = True
            self._retry_times = 0
            logger.tinfo("cluster.enable", id=self.id)
            self._keepalive_lock.release()
        except:
            logger.terror("cluster.enable.timeout", id=self.id)
        finally:
            self._want_enable = False
            if not self._enabled:
                self.retry()

    async def disable(self):
        if not self._enabled:
            logger.debug("cluster want disable again")
            return
        self._keepalive_lock.acquire()
        try:
            await self.emit("disable")
        finally:
            self._enabled = False
            self._failed_keepalive = 0
        logger.tinfo("cluster.disable", id=self.id)

        if self._stop:
            return
        
        self.retry()

    def retry(self):
        if self._enabled or self._want_enable or self._task_group is None:
            return
        self._retry_times += 1
        next = min(3600, self._retry_times * 300)
        logger.tinfo("cluster.retry", id=self.id, time=next)
        utils.schedule_once(self._task_group, self.enable, delay=next)

    async def stop_serve(self):
        self._stop = True
        await self.disable()

class DownloadManager:
    def __init__(
        self,
        missing_files: set[BMCLAPIFile],
        clusters: list[Cluster],
        storages: list[CheckStorage]
    ):
        self._missing_files = missing_files
        self._clusters = clusters
        self._storages = storages
        self._pbar = utils.MultiTQDM(
            total=sum(missing_file.size for missing_file in missing_files),
            description="Download",
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        )
        self._failed = 0
        self._success = 0
        self._cache_dir = ROOT_PATH / "cache"

        self._cache_dir.mkdir(exist_ok=True, parents=True)

    def update_success(self):
        self._success += 1
        self.update_display()
    
    def update_failed(self):
        self._failed += 1
        self.update_display()

    def update_display(self):
        self._pbar.set_postfix_str(f"{self._success}/{len(self._missing_files)}, {self._failed}")
    
    async def download(self):
        configuration = await self.get_configurations()
        logger.tinfo("download.configuration", source=configuration.source, concurrency=configuration.concurrency)
        async with anyio.create_task_group() as task_group:
            queue = utils.Queue()
            for file in self._missing_files:
                queue.put_item(file)
            for _ in range(configuration.concurrency):
                task_group.start_soon(self._download_files, queue, _)

    async def _download_files(
        self,
        files: utils.Queue[BMCLAPIFile],
        worker_id: int
    ):
        async with aiohttp.ClientSession(
            base_url=cfg.base_url,
            headers={
                "Authorization": f"Bearer {await self._clusters[0].get_token()}",
                "User-Agent": USER_AGENT,
            }
        ) as session:
            with self._pbar.sub(0, f"Worker {worker_id}", unit="B", unit_scale=True, unit_divisor=1024) as pbar:
                while len(files) != 0:
                    file = await files.get_item()
                    pbar._tqdm.total = file.size
                    pbar._tqdm.n = 0
                    pbar._tqdm.set_description_str(file.path)
                    pbar._tqdm.refresh()
                    pbar._tqdm.update(0)
                    await self._download_file(file, session, pbar)

    async def _download_file(
        self,
        file: BMCLAPIFile,
        session: aiohttp.ClientSession,
        pbar: utils.SubTQDM
    ):
        last_error = None
        for _ in range(10):
            size = 0
            hash = utils.get_hash_obj(file.hash)
            with tempfile.NamedTemporaryFile(
                dir=self._cache_dir,
            ) as tmp_file:
                print(pbar.position)
                try:
                    async with session.get(
                        file.path
                    ) as resp:
                        while (data := await resp.content.read(1024 * 1024 * 16)):
                            tmp_file.write(data)
                            hash.update(data)
                            inc = len(data)
                            size += inc
                            self._pbar.update(inc)
                            pbar.update(inc)
                        if hash.hexdigest() != file.hash or size != file.size:
                            await anyio.sleep(50)
                            raise Exception(f"hash mismatch, got {hash.hexdigest()} expected {file.hash}")

                except Exception as e:
                    last_error = e
                    self._pbar.update(-size)
                    pbar.update(-size)
                    self.update_failed()
                    continue
                self.update_success()
                await self.upload_storage(file, tmp_file)
                return None
        if last_error is not None:
            raise last_error


    async def upload_storage(
        self,
        file: BMCLAPIFile,
        tmp_file: 'tempfile._TemporaryFileWrapper'
    ):
        missing_storage = [
            storage for storage in self._storages if file in storage.missing_files
        ]
        if len(missing_storage) == 0:
            return
        for storage in missing_storage:
            tmp_file.seek(0)
            await storage.storage.upload(f"download/{file.hash[:2]}/{file.hash}", tmp_file)
            




    async def get_configurations(self):
        configurations: list[OpenBMCLAPIConfiguration] = await utils.gather(*[
            cluster.get_configuration() for cluster in self._clusters
        ])
        # select max concurrency
        return max(configurations, key=lambda x: x.concurrency)

class ClusterManager:
    def __init__(
        self,
    ):
        self._clusters: dict[str, Cluster] = {}
        self._storages = StorageManager()
        self._task_group = None
        self._certificate_type: Optional[CertificateType] = None

    def add_cluster(
        self,
        id: str,
        secret: str
    ):
        self._clusters[id] = Cluster(id, secret)

    def get_cluster(
        self,
        id: str
    ) -> Cluster:
        return self._clusters[id]
    
    @property
    def storages(self):
        return self._storages

    @property
    def clusters(self):
        return list(self._clusters.values())
    
    @property
    def count(self):
        return len(self._clusters)
    
    async def setup(self, task_group: anyio.abc.TaskGroup):
        self._task_group = task_group

        @utils.event.callback("storage_disable")
        async def _(msg: Any):
            for cluster in self.clusters:
                await cluster.disable()
            
        @utils.event.callback("storage_enable")
        async def _(msg: Any):
            for cluster in self.clusters:
                await cluster.enable()

        for cluster in self.clusters:
            await cluster.setup(task_group)

        await self.storages.setup(task_group)

    async def get_files(self) -> set[BMCLAPIFile]:
        # 批量获取 files
        return set().union(
            *await utils.gather(*[
                cluster.get_files() for cluster in self.clusters
            ])
        )

    async def sync(self):
        assert self._task_group is not None

        files = await self.get_files()
        total_size = sum([f.size for f in files])
        if total_size == 0:
            logger.tinfo("cluster.sync.no_files")
            utils.schedule_once(self._task_group, self.sync, 600)
            return
        last_modified = max(files, key=lambda x: x.mtime).mtime
        logger.tinfo("cluster.sync.files", count=len(files), size=units.format_bytes(total_size), last_modified=units.format_datetime_from_timestamp(last_modified))
        
        check_storages = [CheckStorage(storage) for storage in self.storages.storages]
        with utils.MultiTQDM(
            len(check_storages),
            description="Listing files"
        ) as pbar:
            missing_files: set[BMCLAPIFile] = set().union(
                *await utils.gather(*[
                    check_storage.get_missing_files(files, pbar) for check_storage in check_storages
                ])
            )
        if len(missing_files) > 0:
            logger.tinfo("cluster.sync.missing_files", count=len(missing_files), size=units.format_bytes(sum([f.size for f in missing_files])))
            download_manager = DownloadManager(missing_files, self.clusters, check_storages)
            await download_manager.download()
        else:
            logger.tinfo("cluster.sync.no_missing_files")
        
        utils.schedule_once(self._task_group, self.sync, 600)

    async def _sync(self):
        await anyio.sleep(600)
        await self.sync()

    async def serve(self):
        for cluster in self.clusters:
            await cluster.start_serve()

    async def stop(self):
        for cluster in self.clusters:
            await cluster.stop_serve()

    def hit(self, cluster_id: str, bytes: int):
        self._clusters[cluster_id].counter.hits += 1
        self._clusters[cluster_id].counter.bytes += bytes
    
    async def get_response_file(self, hash: str) -> ResponseFile:
        storage = self.storages.get_weight_storage()
        if storage is None:
            logger.twarning("cluster.get_response_file.no_storage")
            return ResponseFile(
                0
            )
        return await storage.get_response_file(hash)