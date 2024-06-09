import asyncio
from asyncio import exceptions
import base64
from collections import defaultdict
from dataclasses import asdict
import hashlib
import hmac
import io
import json
import sys
import time
import traceback
from typing import Any, Optional
import aiofiles
import aiohttp
import pyzstd as zstd
import socketio
import socketio.exceptions
from tqdm import tqdm

from core import certificate, dashboard, logger, socketio_logger, scheduler, statistics, unit, utils, web
from core.api import BMCLAPIFile, DownloadReason, DownloadStatistics, File, FileCheckType, FileContentType, ResponseRedirects, StatsCache, Storage, OpenbmclapiAgentConfiguration, StorageData, StorageWidth, StoragesInfo, WeightedStorage, get_hash, get_hash_content
from core.const import *
from core.exceptions import PutQueueIgnoreError
from core.i18n import locale

import aiowebdav.client as webdav3_client
import aiowebdav.exceptions as webdav3_exceptions

class Token:
    def __init__(self, clusterID: str, clusterSecert: str) -> None:
        self.clusterID = clusterID
        self.clusterSecert = clusterSecert
        self.token = None
        self.ttl = 0
        self.fetch_time = 0
        self.scheduler = None
    async def fetch(self):
        async with aiohttp.ClientSession(
            BASE_URL,
            headers=HEADERS
        ) as session:
            logger.tinfo("cluster.info.token.fetching")
            async with session.get(
                "/openbmclapi-agent/challenge", params={"clusterId": self.clusterID}
            ) as resp:
                resp.raise_for_status()
                challenge = (await resp.json())['challenge']
                signature = hmac.new(
                    CLUSTER_SECERT.encode("utf-8"), digestmod=hashlib.sha256
                )
                signature.update(challenge.encode())
                signature = signature.hexdigest()
            async with session.post(
                "/openbmclapi-agent/token",
                data = {
                    "clusterId": CLUSTER_ID,
                    "challenge": challenge,
                    "signature": signature,
                }
            ) as resp:
                resp.raise_for_status()
                json = await resp.json()
                self.token = json['token']
                self.ttl = json['ttl'] / 1000.0
                self.fetch_time = time.monotonic()
                if self.scheduler is not None:
                    scheduler.cancel(self.scheduler)
                self.scheduler = scheduler.delay(self.fetch, delay=self.ttl / 2)
                tll = utils.format_stime(self.ttl)
                logger.tsuccess("cluster.success.token.fetched", cluster=self.clusterID, tll=tll)
            
    def __str__(self) -> str:
        return str(self.token)
    
    def __repr__(self) -> str:
        return str(self.token)

class FileStorage(Storage):
    def __init__(self, name: str, dir: Path, width: int) -> None:
        super().__init__(name, "file", width)
        self.dir = dir
        if self.dir.is_file():
            raise FileExistsError(f"Cannot copy file: '{self.dir}': Is a file.")
        self.dir.mkdir(exist_ok=True, parents=True)

    async def get(self, hash: str) -> File:
        if self.is_cache(hash):
            file = self.get_cache(hash)
            return file
        path = Path(str(self.dir) + f"/{hash[:2]}/{hash}")
        file = File(hash, path.stat().st_size, FileContentType.EMPTY)
        if CACHE_ENABLE:
            buf = io.BytesIO()
            async with aiofiles.open(path, "rb") as r:
                while data := await r.read(IO_BUFFER):
                    buf.write(data)
            file = File(hash, buf.tell(), time.time(), time.time())
            file.set_data(buf)
        else:
            file.set_data(path)
        if CACHE_ENABLE:
            self.set_cache(hash, file)
        return file

    async def exists(self, hash: str) -> bool:
        return os.path.exists(str(self.dir) + f"/{hash[:2]}/{hash}")

    async def get_size(self, hash: str) -> int:
        return os.path.getsize(str(self.dir) + f"/{hash[:2]}/{hash}")

    async def write(self, hash: str, io: io.BytesIO) -> int:
        Path(str(self.dir) + f"/{hash[:2]}/{hash}").parent.mkdir(
            exist_ok=True, parents=True
        )
        async with aiofiles.open(str(self.dir) + f"/{hash[:2]}/{hash}", "wb") as w:
            await w.write(io.getbuffer())
            return len(io.getbuffer())

    async def get_hash(self, hash: str) -> str:
        h = get_hash(hash)
        async with aiofiles.open(str(self.dir) + f"/{hash[:2]}/{hash}", "rb") as r:
            while data := await r.read(IO_BUFFER):
                if not data:
                    break
                h.update(data)
                await asyncio.sleep(0.001)
        return h.hexdigest()

    async def get_files(self, dir: str) -> list[str]:
        files = []
        if os.path.exists(str(self.dir) + f"/{dir}"):
            with os.scandir(str(self.dir) + f"/{dir}") as session:
                for file in session:
                    files.append(file.name)
        return files

    async def removes(self, hashs: list[str]) -> int:
        success = 0
        for hash in hashs:
            file = str(self.dir) + f"/{hash[:2]}/{hash}"
            if os.path.exists(file):
                os.remove(file)
                success += 1
        return success

    async def get_files_size(self, dir: str) -> int:
        size = 0
        if os.path.exists(str(self.dir) + f"/{dir}"):
            with os.scandir(str(self.dir) + f"/{dir}") as session:
                for file in session:
                    size += file.stat().st_size
        return size
    
class WebDavStorage(Storage):
    def __init__(
        self,
        name: str,
        width: int,
        username: str,
        password: str,
        hostname: str,
        endpoint: str,
        headers: dict[str, Any] = {}
    ) -> None:
        super().__init__(name, "webdav", width)
        self.username = username
        self.password = password
        self.hostname = hostname
        self.endpoint = "/" + endpoint.replace("\\", "/").replace("//", "/").removesuffix("/").removeprefix('/')
        self.files: dict[str, File] = {}
        self.keepalive_file: Optional[File] = None
        self.dirs: list[str] = []
        self.fetch: bool = False
        self.empty = File("", "", 0)
        self.lock = utils.WaitLock()
        self.session = webdav3_client.Client(
            {
                "webdav_login": self.username,
                "webdav_password": self.password,
                "webdav_hostname": self.hostname,
                "User-Agent": USER_AGENT,
            }
        )
        self.session_lock = asyncio.Lock()
        self.get_session_lock = asyncio.Semaphore(LIMIT_SESSION_WEBDAV)
        self.get_session = aiohttp.ClientSession(
            auth=aiohttp.BasicAuth(
                self.username,
                self.password
            ),
            
        )
        scheduler.delay(self._list_all)
        scheduler.repeat(self._keepalive, interval=60)

    async def _keepalive(self):
        async def get_keepalive_file():
            await self._wait_lock()
            self.keepalive_file = (sorted(filter(lambda x: x.size != 0, list(self.files.values())) or [], key=lambda x: x.size) or [None])[0]
            if self.keepalive_file is None:
                disable("no_file")
        def disable(reason, *args, **kwargs):
            if not self.disabled:
                logger.twarn(
                    "cluster.warn.webdav." + reason,
                    *args,
                    **kwargs,
                    hostname=self.hostname, 
                    endpoint=self.endpoint
                )
            storageManager.disable(self)
            self.fetch = False
        async def process_content(resp: aiohttp.ClientResponse) -> bool:
            content = io.BytesIO(await resp.read())
            h = get_hash(self.keepalive_file.hash)
            h.update(content.getbuffer())
            if h.hexdigest() != self.keepalive_file.hash:
                logger.tdebug("cluster.debug.webdav.response", status=resp.status, url=resp.real_url, response=repr(content.getvalue())[2:-1])
                disable("file_hash", status=resp.status, url=resp.real_url, file_hash=h.hexdigest(), file_size=unit.format_bytes(len(content.getbuffer())), hash=self.keepalive_file.hash, hash_size=unit.format_bytes(self.keepalive_file.size))
                return False
            return True
        try:
            hostname = self.hostname
            endpoint = self.endpoint
            await get_keepalive_file()
            if not self.keepalive_file:
                await self._list_all()
            await get_keepalive_file()
            if not self.keepalive_file:
                disable("no_file")
                return
            async with self.session_lock:
                async with self.get_session.get(
                    self.hostname + self._file_endpoint(self.keepalive_file.hash[:2] + "/" + self.keepalive_file.hash),
                    allow_redirects=False
                ) as resp:
                    if resp.status // 100 == 3:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                resp.headers.get("Location")
                            ) as resp:
                                if not await process_content(resp):
                                    return
                    else:
                        if not await process_content(resp):
                            return
            if not self.disabled:
                logger.tsuccess(
                    "cluster.success.webdav.keepalive",
                    hostname=hostname,
                    endpoint=endpoint,
                )
            else:
                storageManager.enable(self)
                logger.tsuccess(
                    "cluster.success.webdav.enabled",
                    hostname=hostname,
                    endpoint=endpoint,
                )
        except webdav3_exceptions.NoConnection:
            disable("no_connection")
        except:
            logger.error(traceback.format_exc())

    async def _execute(self, target):
        try:
            return await asyncio.wait_for(target, timeout=WEBDAV_TIMEOUT)
        except webdav3_exceptions.NoConnection as e:
            hostname = self.hostname
            endpoint = self.endpoint
            logger.twarn(
                "cluster.warn.webdav.no_connection",
                hostname=hostname,
                endpoint=endpoint,
            )
            storageManager.disable(self)
            self.fetch = False
            raise e
        except (
            asyncio.TimeoutError,
            TimeoutError,
            exceptions.TimeoutError,
        ):
            return asyncio.CancelledError
        except Exception as e:
            raise e

    def _file_endpoint(self, file: str):
        return f"{self._download_endpoint()}/{file.removeprefix('/')}".replace(
            "//", "/"
        )

    def _download_endpoint(self):
        return f"{self.endpoint}/download"

    async def _mkdir(self, dirs: str):
        r = await self._execute(self.session.check(dirs))
        if r is asyncio.CancelledError or r:
            return
        await self.session_lock.acquire()
        d = ""
        for dir in dirs.split("/"):
            d += dir
            await self._execute(self.session.mkdir(d))
            d += "/"
        self.session_lock.release()

    async def _list_all(self, force=False):
        if self.fetch and not force:
            return
        if not self.fetch:
            self.lock.acquire()
        self.fetch = True
        def stop(tqdm: Optional[tqdm] = None):
            if tqdm is not None:
                del tqdm
            self.lock.acquire()
            self.fetch = False
            logger.error("无法获取 WebDav 文件列表")
            raise asyncio.CancelledError
        try:
            await self._mkdir(self._download_endpoint())
            r = await self._execute(self.session.list(self._download_endpoint()))
            if r is asyncio.CancelledError:
                stop()
            dirs = r[1:]
            with tqdm(
                total=len(dirs),
                desc=f"[WebDav List Files <endpoint: '{self._download_endpoint()}'>]",
            ) as pbar:
                await dashboard.set_status_by_tqdm("storage.webdav", pbar)
                r = await self._execute(self.session.list(self._download_endpoint()))
                if r is asyncio.CancelledError:
                    return stop(pbar)
                for dir in r[1:]:
                    pbar.update(1)
                    files: dict[str, File] = {}
                    r = await self._execute(
                        self.session.list(
                            self._file_endpoint(
                                dir,
                            ),
                            get_info=True,
                        )
                    )
                    if r is asyncio.CancelledError:
                        return stop(pbar)
                    for file in r[1:]:
                        if file["isdir"]:
                            continue
                        files[file["name"]] = File(
                            file["name"],
                            int(file["size"]),
                            FileContentType.EMPTY
                        )
                        try:
                            await asyncio.sleep(0)
                        except asyncio.CancelledError:
                            return stop(pbar)
                        except Exception as e:
                            raise e
                    for remove in set(
                        file for file in self.files.keys() if file.startswith(dir)
                    ) - set(files.keys()):
                        self.files.pop(remove)
                    self.files.update(files)
                    if dir not in self.dirs:
                        self.dirs.append(dir)
        except:
            logger.error(traceback.format_exc())
        if self.lock is not None:
            self.lock.release()
        return self.files

    async def _wait_lock(self):
        if self.lock is None:
            return
        await self.lock.wait()

    async def get(self, hash: str, start: int = 0, end: int = 0) -> File:
        if self.is_cache(hash):
            file = self.get_cache(hash)
            return file
        try:
            f = File(
                hash,
                hash,
                0,
            )
            session = self.get_session
            async with self.get_session_lock:
                async with session.get(
                    self.hostname + self._file_endpoint(hash[:2] + "/" + hash),
                    allow_redirects=False,
                ) as resp:
                    if resp.status == 200:
                        f.headers = {}
                        for field in (
                            "ETag",
                            "Last-Modified",
                            "Content-Length",
                        ):
                            if field not in resp.headers:
                                continue
                            f.headers[field] = resp.headers.get(field)
                        f.size = int(resp.headers.get("Content-Length", 0))
                        f.set_data(io.BytesIO(await resp.read()))
                        if CACHE_ENABLE:
                            f.expiry = time.time() + CACHE_TIME
                            self.set_cache(hash, f)
                    elif resp.status // 100 == 3:
                        f.size = await self.get_size(hash)
                        f.set_data(resp.headers.get("Location"))
                        expiry = re.search(r"max-age=(\d+)", resp.headers.get("Cache-Control", "")) or 0
                        if max(expiry, CACHE_TIME) == 0:
                            return f
                        f.expiry = time.time() + expiry
                        if CACHE_ENABLE or f.expiry != 0:
                            self.set_cache(hash, f)
            return f
        except Exception:
            storageManager.disable(self)
            logger.error(traceback.format_exc())

    async def exists(self, hash: str) -> bool:
        await self._wait_lock()
        if not self.fetch:
            self.fetch = True
            await self._list_all()
        return hash in self.files

    async def get_size(self, hash: str) -> int:
        await self._wait_lock()
        return self.files.get(hash, self.empty).size

    async def write(self, hash: str, io: io.BytesIO) -> int:
        path = self._file_endpoint(f"{hash[:2]}/{hash}")
        await self._mkdir(self._file_endpoint(f"{hash[:2]}"))
        await self._execute(self.session.upload_to(io.getbuffer(), path))
        self.files[hash] = File(hash, len(io.getbuffer()), FileContentType.EMPTY)
        return self.files[hash].size

    async def get_files(self, dir: str) -> list[str]:
        await self._wait_lock()
        return list((hash for hash in self.files.keys() if hash.startswith(dir)))

    async def get_hash(self, hash: str) -> str:
        h = get_hash(hash)
        r = await self._execute(
            self.session.download_iter(self._file_endpoint(f"{hash[:2]}/{hash}"))
        )
        if r is asyncio.CancelledError:
            return
        async for data in r:
            h.update(data)
        return h.hexdigest()

    async def get_files_size(self, dir: str) -> int:
        await self._wait_lock()
        return sum(
            (file.size for hash, file in self.files.items() if hash.startswith(dir))
        )

    async def removes(self, hashs: list[str]) -> int:
        success = 0
        for hash in hashs:
            #await self._execute(
            #    self.session.clean(self._file_endpoint(f"{hash[:2]}/{hash}"))
            #)
            success += 1
        return success

class Cluster:
    def __init__(self, clusterID: str, clusterSecert: str) -> None:
        self.clusterID = clusterID
        self.clusterSecert = clusterSecert
        self.token = Token(self.clusterID, self.clusterSecert)
        self.storages = StorageManager(self)
        self.sio: socketio.AsyncClient = None
        self.byoc = BYOC
        self.cert_expires: float = 0
        self.retry_timer = None
        self.keepalive_timer = None
        self.enabled = False

    async def __call__(self) -> Any:
        try:
            await self.token.fetch()
        except:
            return self
        await self.socketio_init()
        if await self.storages.start_check() is asyncio.CancelledError or await self.cluster_enable() is asyncio.CancelledError:
            return self
        return self
    
    def storage_cache_stats(self):
        stats = asdict(StatsCache())
        for storage in self.storages.storages:
            for key, value in asdict(storage.get_cache_stats()).items():
                stats[key] += value
        return StatsCache(**stats)

    async def cluster_keepalive(self):
        cur_storages = statistics.get_sync_storages()
        data = {"hits": 0, "bytes": 0}
        for storage in cur_storages:
            data["hits"] += storage.hit
            data["bytes"] += storage.bytes
        try:
            err, ack = await self.socketio_emit_with_ack(
                "keep-alive", {"time": int(time.time() * 1000), **{k: max(0, v) for k, v in data.items()}}
            )
            if ack:
                ping = int((time.time() - utils.parse_iso_time(ack).timestamp()) * 1000)
                storage_data = {"hits": 0, "bytes": 0}
                for storage in cur_storages:
                    storage_data["hits"] += storage.hit
                    storage_data["bytes"] += storage.bytes
                statistics.sync(cur_storages)
                hits = unit.format_number(storage_data["hits"])
                bytes = unit.format_bytes(storage_data["bytes"])
                storage_count = len(cur_storages)
                logger.tsuccess(
                    "cluster.success.keepalive",
                    hits=hits,
                    bytes=bytes,
                    count=storage_count,
                    ping=ping,
                )
                cur_storages.clear()
            else:
                await self.cluster_retry()
                return
        except asyncio.TimeoutError:
            ...

    async def cluster_retry(self):
        if self.enabled:
            await self.cluster_disable()
        scheduler.cancel(self.retry_timer)
        self.retry_timer = scheduler.delay(self.cluster_enable, delay=60)
    async def cluster_cert(self, ):
        if self.byoc:
            return
        err, ack = await self.socketio_emit_with_ack(
            "request-cert"
        )
        if err:
            logger.debug("获取证书失败：", err)
            return
        certificate.load_text(ack["cert"], ack["key"])
        self.cert_expires = utils.parse_iso_time(ack["expires"])
    async def cluster_enable(self):
        try:
            err, ack = await self.socketio_emit_with_ack("enable", {
                "host": PUBLIC_HOST,
                "port": PUBLIC_PORT or PORT,
                "version": API_VERSION,
                "noFastEnable": True,
                "flavor": {
                    "runtime": f"python/{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} {VERSION}",
                    "storage": "+".join((key for key, value in asdict(self.storages.get_storage_info(available=True)).items() if key != "total" and value != 0)),
                    **asdict(self.storages.get_storage_info(available=True))
                }
            }, timeout=600)
            if err:
                logger.error(self.cluster_error(err))
                await self.cluster_retry()
                return
            if ack:
                self.enabled = True
                logger.tinfo("cluster.info.cluster.hosting", id=self.clusterID, port=PUBLIC_PORT or PORT)
                self.keepalive_timer = scheduler.repeat(self.cluster_keepalive, interval=60)
        except asyncio.CancelledError:
            return asyncio.CancelledError
        except asyncio.TimeoutError:
            logger.error("注册节点超时")
            await self.cluster_retry()
        
    async def cluster_disable(self, wait: bool = False):
        scheduler.cancel(self.keepalive_timer)
        try:
            if wait:
                await self.socketio_emit_with_ack("disable")
            else:
                await self.socketio_emit("disable")
            return True
        except:
            self.enabled = False
            return True

    async def cluster_setup(self):
        def check_sign(hash: str, s: str, e: str):
            return SIGN_SKIP or utils.check_sign(hash, self.clusterSecert, s, e)
        app = web.app
        @app.get("/measure/{size}")
        async def _(config: web.ResponseConfiguration, size: int = 1, s: str = "", e: str = ""):
            if not check_sign(f"/measure/{size}", s, e):
                return web.Response(status_code=401)
                return
            config.length = 1024 * 1024 * size
            #for _ in range(size):
            #    yield b'\x00' * 1024 * 1024
            return web.RedirectResponse("https://node-36-156-121-26.speedtest.cn:51090/download?size=10485760&r=0.0917991197210346")
        def empty_file(hash: str) -> File:
            return File(
                hash=hash,
                size=0,
                type=FileContentType.EMPTY
            )
        status_text = {
            statistics.Status.FORBIDDEN: ("Forbidden", 403),
            statistics.Status.ERROR: ("Internet Server Error", 500),
            statistics.Status.NOTEXISTS: ("Not Found", 404),
        }

        @app.get("/download/{hash}")
        async def _(request: web.Request, config: web.ResponseConfiguration, hash: str, s: str = "", e: str = ""):
            def hit(status: statistics.Status, storage: Optional[Storage], file: Optional[File], length: Optional[int] = 0):
                statistics.hit(
                    **{
                        "storage": storage,
                        "file": file or empty_file(hash),
                        "length": length,
                        "ip": request.get_ip(),
                        "ua": request.get_user_agent(),
                        "status": status
                    }
                )
                if status in status_text:
                    status_response = status_text[status]
                    return web.Response(status_response[0], status_code=status_response[1])
            if not check_sign(hash, s, e):
                return hit(statistics.Status.FORBIDDEN)
            if self.storages.is_disabled:
                return hit(statistics.Status.ERROR)
            storage = await self.storages.get_available(hash)
            length = None
            name = {}
            if request.get_url_params().get("name"):
                name["Content-Disposition"] = (
                    f"attachment; filename={request.get_url_params().get('name')}"
                )
            start_bytes, end_bytes = 0, None
            range_str = await request.get_headers("range", "")
            range_match = re.search(r"bytes=(\d+)-(\d+)", range_str, re.S) or re.search(
                r"bytes=(\d+)-", range_str, re.S
            )
            if range_match:
                start_bytes = int(range_match.group(1)) if range_match else 0
                if range_match.lastindex == 2:
                    end_bytes = int(range_match.group(2))
                    length = end_bytes - start_bytes + 1
            if not storage or not storage.exists:
                bmclapifile = BMCLAPIFile(hash, hash, None, 0)
                try:
                    logger.tdebug("cluster.debug.download_temp.downloading", hash=hash)
                    file, result = await self.storages._download(bmclapifile, miss_storage={bmclapifile: self.storages.available_storages}, center=True)
                    logger.tdebug("cluster.debug.download_temp.downloaded", hash=hash)
                    if length is None:
                        length = len(result.getbuffer())
                    file = File(
                        hash=hash,
                        size=len(result.getbuffer()),
                        type=FileContentType.DATA,
                    ).set_data(result)
                    hit(statistics.Status.SUCCESS if start_bytes == 0 and end_bytes is None else statistics.Status.PARTIAL, None, file, length)
                    return web.Response(
                        result.getbuffer() or {}, response_configuration=config
                    ).set_headers(name)
                except:
                    logger.tdebug("cluster.debug.download_temp.failed_download", hash=hash)
                    return hit(statistics.Status.NOTEXISTS, None, None, None)
            data = await storage.storage.get(hash)
            if length is None:
                length = data.size
            config.access_log = DOWNLOAD_ACCESS_LOG
            if data.is_url() and isinstance(data.get_path(), str):
                hit(statistics.Status.REDIRECT, storage.storage, data, length)
                return web.RedirectResponse(str(data.get_path()), response_configuration=config).set_headers(name)
            hit(statistics.Status.SUCCESS if start_bytes == 0 and end_bytes is None else statistics.Status.PARTIAL, storage.storage, data, length)
            return web.Response(
                data.get_data().getbuffer() if not data.is_path() else data.get_path(), headers=data.headers or {}, response_configuration=config
            ).set_headers(name)
            

        dir = Path("./bmclapi_dashboard/")
        dir.mkdir(exist_ok=True, parents=True)
        app.mount_resource(web.Resource("/", dir, show_dir=False))
    
        @app.get("/pages/{name}/{sub}")
        @app.get("/pages/{name}")
        async def _(request: web.Request, name: str, sub: str = ""):
            return Path(f"./bmclapi_dashboard/index.html")
    
        @app.post("/pages/{name}/{sub}")
        @app.post("/pages/{name}")
        async def _(request: web.Request, namespace: str):
            data = await dashboard.process(
                namespace, await request.json()
            )
            return web.Response({"data": data})
    
        @app.websocket("/pages/{name}/{sub}")
        @app.websocket("/pages/{name}")
        async def _(request: web.Request, ws: web.WebSocket):
            dashboard.websockets.append(ws)
            async for raw_data in ws:
                data: dict[str, Any] = json.loads(raw_data)
                await ws.send(
                    {
                        'id': data.get('id', -1),
                        'namespace': data['namespace'],
                        'data': dashboard.parse_json(
                            await dashboard.process(
                                data['namespace'], data.get('data')
                            )
                        )
                    }
                )
            dashboard.websockets.remove(ws)
    
        @app.get("/config/dashboard.js")
        async def _():
            return f"const __CONFIG__={json.dumps(DASHBOARD_CONFIGURATION)}"
    
        @app.get("/auth")
        async def _(request: web.Request):
            auth = (await request.get_headers("Authorization")).split(" ", 1)[1]
            try:
                info = json.loads(base64.b64decode(auth))
            except:
                return web.Response("Unauthorized", status_code=401)
            if (
                info["username"] != DASHBOARD_USERNAME
                or info["password"] != DASHBOARD_PASSWORD
            ):
                return web.Response("Unauthorized", status_code=401)
            token = dashboard.generate_token(request)
            return web.Response(
                DASHBOARD_USERNAME,
                cookies=[web.Cookie("auth", token.value, expires=int(time.time() + 86400))],
            )
    
        @app.post("/api/{name}")
        async def _(request: web.Request, name: str):
            if name == "auth":
                auth_cookie = (await request.get_cookies()).get("auth") or None
                auth = dashboard.token_isvaild(auth_cookie.value if auth_cookie else None)
                if not auth:
                    return None
                else:
                    return DASHBOARD_USERNAME
            data = {"content": ""}
            try:
                data = (await request.json()) or {}
                if "content" not in data:
                    data = {"content": ""}
            except:
                ...
            return await dashboard.process(name, data.get("content"))
    
        app.redirect("/", "/pages/")
    
        @app.get("/robot.txt")
        def _():
            return "User-agent: * Disallow: /"


    def cluster_error(self, err):
        if isinstance(err, dict) and 'message' in err:
            return str(err['message'])
        return str(err)
    

    async def socketio_disconnect(self):
        if not self.sio.connected:
            return
        await self.cluster_disable(True)
        await self.sio.disconnect()
    async def socketio_init(self):
        if self.sio is not None:
            return
        self.sio = socketio.AsyncClient(
            logger=socketio_logger,
            engineio_logger=socketio_logger
        )
        await self.socketio_connect()
    async def socketio_connect(self):
        if self.sio.connected:
            return
        await self.sio.connect(
            BASE_URL,
            headers=HEADERS,
            auth={"token": str(self.token)},
            transports=["websocket"],
        )
        await self.cluster_cert()
    async def socketio_message(self, channel, data: list[Any], callback=None):
        if len(data) == 1:
            data.append(None)
        err, ack = data
        if channel != "request-cert":
            logger.tdebug("cluster.debug.cluster.emit.recv", channel=channel, data=data)
        if callback is None:
            return
        try:
            await callback(err, ack)
        except:
            logger.error(traceback.format_exc())
    async def socketio_emit(self, channel, data=None, callback=None):
        async def _():
            try:
                await callback(*(await self.socketio_emit_with_ack(channel, data)))
            except:
                logger.error(traceback.format_exc())
        scheduler.delay(_)

    async def socketio_emit_with_ack(self, channel, data=None, timeout: Optional[float] = None):
        logger.tdebug(
            "cluster.debug.cluster.emit.send",
            channel=channel,
            data=data,
        )
        wait_lock = asyncio.get_event_loop().create_future()
        timer = None
        def callback(data: list[Any]):
            if wait_lock._exception is not None:
                return
            if len(data) == 1:
                data.append(None)
            err, ack = data
            if channel != "request-cert":
                logger.tdebug("cluster.debug.cluster.emit.recv", channel=channel, data=data)
            wait_lock.set_result((err, ack))
            scheduler.cancel(timer)
        try:
            await self.sio.emit(
                channel,
                data,
                callback=callback,
            )
            if timeout is not None:
                timer = scheduler.delay(wait_lock.set_exception, args=(asyncio.TimeoutError, ), delay=timeout)
            try:
                await wait_lock
                scheduler.cancel(timer)
                return wait_lock.result() or (True, None)
            except asyncio.CancelledError:
                wait_lock.cancel()
                scheduler.cancel(timer)
                return True, None
        except socketio.exceptions.BadNamespaceError:
            await self.socketio_disconnect()
            logger.tdebug("cluster.debug.cluster.socketio.disconnect")
            await self.token.fetch()
            await self.socketio_connect()

class StorageManager:
    def __init__(self, cluster: Cluster) -> None:
        self.storages: list[Storage] = []
        self.available_storages: list[Storage] = []
        self.widths: WeightedStorage = WeightedStorage()
        self.files: set[BMCLAPIFile] = set()
        self.lastModified = 0
        self.cluster = cluster
        self.queues: asyncio.Queue[BMCLAPIFile] = asyncio.Queue()
        self.stats: DownloadStatistics = None
        self.errors: defaultdict[BMCLAPIFile, int] = defaultdict(int)
        self.sem: asyncio.Semaphore = None
        self.check_timer = None
        self.storage_cur = 0
        if FILECHECK == "hash":
            self.check_type_handler = self._hash
            self.check_type = FileCheckType.HASH
        elif FILECHECK == "size":
            self.check_type_handler = self._size
            self.check_type = FileCheckType.SIZE
        else:
            self.check_type_handler = self._hash
            self.check_type = FileCheckType.EXISTS
        logger.tinfo("cluster.info.check_files.check_type", type=self.check_type.name)

    def add_storage(self, storage: Storage):
        self.storages.append(storage)
        self.widths.add(StorageWidth(storage))
        storageManager.add(storage, self)
        if not storage.disabled:
            self.available_storages.append(storage)

    def disabled(self, storage: Storage):
        if storage in self.available_storages:
            self.available_storages.remove(storage)
    
    def enable(self, storage: Storage):
        if storage not in self.available_storages:
            self.available_storages.append(storage)
            if not self.cluster.enabled:
                scheduler.delay(self.cluster.cluster_retry)

    @property
    def is_disabled(self):
        return len(self.available_storages) == 0

    async def get_available(self, hash: str) -> Optional[StorageData]:
        if self.is_disabled:
            return None
        return await self.widths.get(hash)

    async def fetch(self):
        async with aiohttp.ClientSession(
            BASE_URL,
            headers={
                **HEADERS,
                "Authorization": f"Bearer {self.cluster.token}"
            }
        ) as session:
            async with session.get(
                "/openbmclapi/files", params={
                    "lastModified": self.lastModified * 1000.0
                }
            ) as resp:
                if resp.status == 204:
                    logger.tinfo(
                        "cluster.info.get_files.info",
                        time=utils.parse_time_to_gmt(self.lastModified),
                        count=unit.format_number(0),
                    )
                    return set()
                data = io.BytesIO(zstd.decompress(await resp.read()))
                before = self.files.copy()
                self.files.update([
                    BMCLAPIFile(
                        self.read_string(data),
                        self.read_string(data),
                        self.read_long(data),
                        self.read_long(data)
                    ) for _ in range(self.read_long(data))
                ])
                after = self.files - before
                self.lastModified = max(self.files, key=lambda x: x.mtime).mtime / 1000.0
                modified = utils.parse_time_to_gmt(self.lastModified)
                logger.tinfo(
                    "cluster.info.get_files.info",
                    time=modified,
                    count=unit.format_number(len(self.files)),
                )
                return after
    
    async def get_configuration(self) -> OpenbmclapiAgentConfiguration:
        async with aiohttp.ClientSession(
            BASE_URL,
            headers={
                **HEADERS,
                "Authorization": f"Bearer {self.cluster.token}"
            }
        ) as session:
            async with session.get(
                "/openbmclapi/configuration"
            ) as resp:
                return OpenbmclapiAgentConfiguration(**(await resp.json())['sync'])

    def read_long(self, stream: io.BytesIO):
        b = ord(stream.read(1))
        n = b & 0x7F
        shift = 7
        while (b & 0x80) != 0:
            b = ord(stream.read(1))
            n |= (b & 0x7F) << shift
            shift += 7
        return (n >> 1) ^ -(n & 1)

    def read_string(self, stream: io.BytesIO):
        return stream.read(self.read_long(stream)).decode("utf-8")

    async def start_check(self):
        start = time.monotonic()
        files = await self.fetch()
        if files:
            try:
                miss = await self.check(files)
                if miss is asyncio.CancelledError:
                    return miss
            except asyncio.CancelledError:
                return asyncio.CancelledError
            if len(set().union(*miss.values())) != 0:
                logger.tinfo(
                    "cluster.info.check_files.missing",
                    count=unit.format_number(len(set().union(*miss.values()))),
                )
                try:
                    await self.download(miss, await self.get_configuration())
                except asyncio.CancelledError:
                    return asyncio.CancelledError 
            else:
                storages = len(self.available_storages)
                file_count = len(files) * storages
                file_size = sum((file.size for file in files)) * storages
                logger.tsuccess(
                    "cluster.success.check_files.finished", count=file_count, size=file_size
                )
        end = time.monotonic()
        logger.tsuccess(
            "cluster.info.download.finished",
            time=utils.format_stime(end - start)
        )
        if self.check_timer is not None:
            scheduler.cancel(self.check_timer)
        self.check_timer = scheduler.delay(self.start_check, delay=1800)

    async def check(self, files: set[BMCLAPIFile]) -> dict[Storage, set[BMCLAPIFile]]:
        miss_storages: dict[Storage, set[BMCLAPIFile]] = {}
        storages = self.available_storages
        with tqdm(
            desc=locale.t("cluster.tqdm.desc.check_files"),
            total=len(files) * len(storages),
            unit=locale.t("cluster.tqdm.unit.file"),
            unit_scale=True,
        ) as pbar:
            try:
                for storage, storage_result in zip(storages, await asyncio.gather(*[asyncio.create_task(self._check_by_storage(files, storage, pbar)) for storage in storages])):
                    miss_storages[storage] = storage_result
            except asyncio.CancelledError:
                return asyncio.CancelledError
        if not COPY_FROM_OTHER_STORAGE and len(storages) >= 2:
            copy_storage: defaultdict[Storage, dict[BMCLAPIFile, Storage]] = defaultdict(dict)
            miss_bytes = 0
            for storage, files in miss_storages.items():
                for other_storage, other_files in miss_storages.items():
                    if other_storage == storage:
                        continue
                    for file in files:
                        if file not in other_files:
                            copy_storage[storage][file] = other_storage
                            miss_bytes += file.size
            if miss_bytes != 0:
                with tqdm(
                    total=miss_bytes,
                    desc=locale.t(
                        "cluster.tqdm.desc.copying_files_from_other_storages"
                    ),
                    unit="B",
                    unit_divisor=1024,
                    unit_scale=True,
                ) as pbar:
                    for storage, failed in zip(copy_storage.keys(), await asyncio.gather(*[asyncio.create_task(self.copy_storage(origin, files_storage, pbar)) for origin, files_storage in copy_storage.items()])):
                        miss_storages[storage] = failed
        return miss_storages

    async def copy_storage(self, origin_storage: Storage, files_storage: dict[BMCLAPIFile, Storage], pbar: tqdm):
        queue: asyncio.Queue[tuple[BMCLAPIFile, Storage]] = asyncio.Queue()
        for file, storage in files_storage.items():
            await queue.put((file, storage))
        return set().union(*(await asyncio.gather(*[asyncio.create_task(self._copy_storage(origin_storage, queue, pbar))])))
        
    async def _copy_storage(self, origin_storage: Storage, queue: asyncio.Queue[tuple[BMCLAPIFile, Storage]], pbar: tqdm):
        failed: set[BMCLAPIFile] = set()
        while not queue.empty():
            file, storage = await queue.get()
            data = await self._get_storage_data(storage, file)
            if not data:
                failed.add(file)
                continue
            pbar.update(file.size)
            await origin_storage.write(file.hash, data)
        return failed

    async def _get_storage_data(self, storage: Storage, file: BMCLAPIFile) -> Optional[io.BytesIO]:
        data = await storage.get(file.hash)
        if not data or data.type == FileContentType.EMPTY:
            return None
        content = io.BytesIO()
        if data.type == FileContentType.DATA:
            content.write(data.get_data().getbuffer())
        if data.type == FileContentType.PATH:
            async with aiofiles.open(data.get_path(), "rb") as r:
                await r.readinto(content)
        elif data.type == FileContentType.URL:
            async with aiohttp.ClientSession(
                headers=HEADERS
            ) as session:
                async with session.get(
                    data.get_path()
                ) as resp:
                    if not resp.ok:
                        return None
                    content.write(resp.read())
        content.seek(0)
        if get_hash_content(file.hash, content) != file.hash:
            return None
        return content

    async def _exists(self, file: BMCLAPIFile, storage: Storage):
        return await storage.exists(file.hash)

    async def _size(self, file: BMCLAPIFile, storage: Storage):
        return (
            await storage.exists(file.hash)
            and await storage.get_size(file.hash) == file.size
        )

    async def _hash(self, file: BMCLAPIFile, storage: Storage):
        return (
            await storage.exists(file.hash)
            and await storage.get_hash(file.hash) == file.hash
        )
    
    async def _check_by_storage(self, files: set[BMCLAPIFile], storage: Storage, pbar: tqdm) -> set[BMCLAPIFile]:
        queue: asyncio.Queue[BMCLAPIFile] = asyncio.Queue()
        for file in files:
            await queue.put(file)
        return set().union(*(await asyncio.gather(*[asyncio.create_task(self._check_storage_file(queue, storage, pbar)) for _ in range(32)])))

    async def _check_storage_file(self, queue: asyncio.Queue[BMCLAPIFile], storage: Storage, pbar: tqdm) -> set[BMCLAPIFile]:
        miss = set()
        while not queue.empty():
            file = await queue.get()
            if not await self.check_type_handler(file, storage):
                miss.add(file)
            pbar.update(1)
        return miss
          
    def get_storage_info(self, available: bool = False) -> StoragesInfo:
        info = StoragesInfo()
        for storage in self.storages if not available else self.available_storages:
            if isinstance(storage, FileStorage):
                info.file += 1
            elif isinstance(storage, WebDavStorage):
                info.webdav += 1
        info.total = info.file + info.webdav
        return info
    
    async def download(self, storages: dict[Storage, set[BMCLAPIFile]], configuration: OpenbmclapiAgentConfiguration):
        miss_storage: defaultdict[BMCLAPIFile, list[Storage]] = defaultdict(list)
        for storage, files in storages.items():
            for file in files:
                if file not in miss_storage:
                    await self.queues.put(file)
                miss_storage[file].append(storage)
        if not DOWNLOAD_CONFIGURATION:
            logger.tinfo("cluster.info.download.configuration", **asdict(configuration))
            self.sem = asyncio.Semaphore(configuration.concurrency)
        self.stats = DownloadStatistics(
            total=len(files)
        )
        tasks = []
        sessions: list[aiohttp.ClientSession] = []
        step = min(32, MAX_DOWNLOAD)
        with tqdm(
            desc=locale.t("cluster.tqdm.desc.download"),
            unit="B",
            unit_divisor=1024,
            total=sum((file.size for file in files)),
            unit_scale=True,
        ) as pbar:
            self.update_tqdm(pbar)
            for _ in range(0, max(1, MAX_DOWNLOAD), step):
                session = await self.get_session()
                sessions.append(session)
                for _ in range(step):
                    tasks.append(asyncio.create_task(self._downloads(pbar, session, miss_storage)))
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                ...
        for session in sessions:
            await session.close()

    async def get_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            BASE_URL,
            headers={
                **HEADERS,
                "Authorization": f"Bearer {self.cluster.token}"
            }
        )

    async def _downloads(self, pbar: tqdm, session: aiohttp.ClientSession, miss_storage: defaultdict[BMCLAPIFile, list[Storage]]):
        while not self.queues.empty():
            file = await self.queues.get()
            try:
                await self._download(file, pbar, miss_storage, session)
                self.stats.downloaded += 1
                self.update_tqdm(pbar)
            except asyncio.CancelledError:
                return
            except:
                self.stats.failed += 1
                await self.queues.put(file)

    async def _download(self, file: BMCLAPIFile, pbar: tqdm = None, miss_storage: defaultdict[BMCLAPIFile, list[Storage]] = defaultdict(), session: aiohttp.ClientSession = None, center: bool = False) -> tuple[BMCLAPIFile, io.BytesIO]:
        close_session = None
        if session is None:
            close_session = session = await self.get_session()
        path: str = file.path if not center else f"/openbmclapi/download/{file.hash}"
        resp = None
        content = io.BytesIO()
        length: int = 0
        def _error():
            return {
                "pbar": pbar,
                "length": length,
                "content": content,
                "session": close_session,
                "file": file,
                "resp": resp
            }
        try:
            if self.sem is not None:
                async with self.sem:
                    resp = await session.get(path)
            else:
                resp = await session.get(path)
            if not resp.ok:
                await self._download_error(reason=DownloadReason.STATUS, **_error())
            cur_length: int = 0
            while (data := await resp.content.read(min(IO_BUFFER, (max(file.size - length, 1) if file.size is not None else IO_BUFFER)))):
                if not data:
                    break
                content.write(data)
                cur_length = len(data)
                length += cur_length
                if pbar is not None:
                    self.stats.total_size += cur_length
                    pbar.update(len(data))
            hash = get_hash_content(file.hash, content)
            content.seek(0)
            if hash != file.hash:
                await self._download_error(reason=DownloadReason.HASH, **_error())
            if await self.write_storage(miss_storage[file], file, content):
                await self._download_error(reason=DownloadReason.STORAGE, **_error())
        except asyncio.CancelledError:
            raise asyncio.CancelledError
        except PutQueueIgnoreError as e:
            raise e
        except:
            await self._download_error(reason=DownloadReason.NETWORK, **_error())
        finally:
            if resp:
                resp.close()
            if close_session is not None:
                await close_session.close()
        return (file, content)
    
    async def write_storage(self, storages: list[Storage], file: BMCLAPIFile, content: io.BytesIO):
        failed = False
        for storage in storages:
            r = await storage.write(file.hash, content)
            if file.size != None:
                failed = failed or r != file.size
        return failed

    def update_tqdm(self, pbar: tqdm):
        pbar.set_postfix_str(f"{unit.format_number(self.stats.downloaded)}/{unit.format_number(self.stats.total)}, {unit.format_number(self.stats.failed)}")

    async def _download_error(self, file: BMCLAPIFile, reason: DownloadReason, pbar: tqdm, length: int, resp: Optional[aiohttp.ClientResponse], content: Optional[io.BytesIO], session: aiohttp.ClientSession, hash: str = None):
        if session is not None:
            await session.close()
        if pbar is not None:
            pbar.update(-length)
            self.stats.failed += 1
            self.update_tqdm(pbar)
        responses: list[aiohttp.ClientResponse] = []
        if resp is not None:
            responses.append(resp)
            for resp in resp.history:
                responses.append(resp)
        msg = []
        history = list((ResponseRedirects(resp.status, str(resp.real_url)) for resp in responses))
        source = "主控" if len(history) == 1 else "节点"
        for history in history:
            msg.append(f"> {history.status} | {history.url}")
        history = '\n'.join(msg)
        body = "<BINARY DATA>"
        if "text" in resp.content_type and ((hash is not None and file.hash != hash) or hash is None) and len(content.getbuffer()) <= 256:
            body = content.getvalue().decode("utf-8", errors="ignore")
        logger.terror("cluster.error.download.failed", hash=file.hash, size=unit.format_bytes(file.size or -1), 
                      source=source, host=responses[-1].host, status=responses[-1].status, history=history, reason=locale.t(f"cluster.error.download.failed.{reason.value}"), body=body)
        if not resp.closed:
            resp.close()
        raise PutQueueIgnoreError

class TotalStorageManager:
    def __init__(self) -> None:
        self.storages: dict[Storage, StorageManager] = {}
    def add(self, storage: Storage, manager: StorageManager):
        self.storages[storage] = manager
    def disable(self, storage: Storage):
        if storage not in self.storages:
            return
        self.storages[storage].disabled(storage)
    def enable(self, storage: Storage):
        if storage not in self.storages:
            return
        self.storages[storage].enable(storage)
storageManager = TotalStorageManager()
cluster: Cluster = None
async def init():
    global cluster
    cluster = Cluster(CLUSTER_ID, CLUSTER_SECERT)
    for storage in STORAGES:
        if storage.type == "file":
            cluster.storages.add_storage(
                FileStorage(storage.name, Path(storage.path), storage.width)
            )
        elif storage.type == "webdav":
            cluster.storages.add_storage(
                WebDavStorage(
                    storage.name,
                    storage.width,
                    storage.kwargs["username"],
                    storage.kwargs["password"],
                    storage.kwargs["endpoint"],
                    storage.path,
                    storage.kwargs.get("headers", {
                        "User-Agent": USER_AGENT,
                    })
                )
            )
    logger.tinfo(
        "cluster.info.cluster.storage_count",
        **asdict(cluster.storages.get_storage_info())
    )
    await cluster.cluster_setup()
    scheduler.delay(cluster.__call__)
async def exit():
    global cluster
    await cluster.socketio_disconnect()
    logger.success("已正常下线")