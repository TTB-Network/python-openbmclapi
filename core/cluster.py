import asyncio
import base64
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback
import aiofiles
import aiohttp
from typing import Any, Optional
import socketio
from tqdm import tqdm
from core.config import Config
from core import certificate, dashboard, system, unit
from core.timer import Task, Timer
import pyzstd as zstd
import core.utils as utils
import core.stats as stats
import core.web as web
from core.logger import logger
import plugins

from core.api import (
    File,
    BMCLAPIFile,
    StatsCache,
    Storage,
    get_hash,
)

VERSION = "1.9.8"
API_VERSION = "1.9.8"
USER_AGENT = f"openbmclapi-cluster/{API_VERSION} python-openbmclapi/{VERSION}"
BASE_URL = "https://openbmclapi.bangbang93.com/"
CLUSTER_ID: str = Config.get("cluster.id")
CLUSTER_SECERT: str = Config.get("cluster.secret")
IO_BUFFER: int = Config.get("advanced.io_buffer")
MAX_DOWNLOAD: int = max(1, Config.get("download.threads"))
BYOC: bool = Config.get("cluster.byoc")
PUBLIC_HOST: str = Config.get("cluster.public_host")
PUBLIC_PORT: int = Config.get("cluster.public_port")
PORT: int = Config.get("web.port")
CACHE_BUFFER: int = 1024 * 1024 * 512
CACHE_TIME: int = 1800
CHECK_CACHE: int = 60
SIGN_SKIP: bool = False
DASHBOARD_USERNAME: str = Config.get("dashboard.username")
DASHBOARD_PASSWORD: str = Config.get("dashboard.password")


class TokenManager:
    def __init__(self) -> None:
        self.token = None

    async def fetchToken(self):
        async with aiohttp.ClientSession(
            headers={"User-Agent": USER_AGENT}, base_url=BASE_URL
        ) as session:
            logger.info("Fetching token...")
            try:
                async with session.get(
                    "/openbmclapi-agent/challenge", params={"clusterId": CLUSTER_ID}
                ) as req:
                    req.raise_for_status()
                    challenge: str = (await req.json())["challenge"]

                signature = hmac.new(
                    CLUSTER_SECERT.encode("utf-8"), digestmod=hashlib.sha256
                )
                signature.update(challenge.encode())
                signature = signature.hexdigest()

                data = {
                    "clusterId": CLUSTER_ID,
                    "challenge": challenge,
                    "signature": signature,
                }

                async with session.post("/openbmclapi-agent/token", json=data) as req:
                    req.raise_for_status()
                    content: dict[str, Any] = await req.json()
                    self.token = content["token"]
                    Timer.delay(
                        self.fetchToken, delay=float(content["ttl"]) / 1000.0 - 600
                    )
                    logger.info("Fetched token.")

            except aiohttp.ClientError as e:
                logger.error(f"An error occured whilst fetching token: {e}.")

    async def getToken(self) -> str:
        if not self.token:
            await self.fetchToken()
        return self.token or ""


class ParseFileList:
    def __init__(self, data) -> None:
        self.data = io.BytesIO(data)
        self.files = []
        for _ in range(self.read_long()):
            self.files.append(
                BMCLAPIFile(self.read_string(), self.read_string(), self.read_long())
            )

    def read_long(self):
        b = ord(self.data.read(1))
        n = b & 0x7F
        shift = 7
        while (b & 0x80) != 0:
            b = ord(self.data.read(1))
            n |= (b & 0x7F) << shift
            shift += 7
        return (n >> 1) ^ -(n & 1)

    def read_string(self):
        return self.data.read(self.read_long()).decode("utf-8")


class FileDownloader:
    def __init__(self) -> None:
        self.files = []
        self.queues: asyncio.Queue[BMCLAPIFile] = asyncio.Queue()
        self.storages = []

    async def get_files(self) -> list[BMCLAPIFile]:
        async with aiohttp.ClientSession(
            base_url=BASE_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {await token.getToken()}",
            },
        ) as session:
            async with session.get(
                "/openbmclapi/files", data={"responseType": "buffer", "cache": ""}
            ) as req:
                req.raise_for_status()
                logger.info("Requested filelist.")
                return ParseFileList(zstd.decompress(await req.read())).files

    async def _download(self, pbar: tqdm, session: aiohttp.ClientSession):
        while not self.queues.empty():
            file = await self.queues.get()
            hash = get_hash(file.hash)
            size = 0
            filepath = Path("./cache/download/" + file.hash[:2] + "/" + file.hash)
            if filepath.exists() and filepath.stat().st_size == size:
                await self._mount_file(file)
            try:
                async with session.get(file.path) as resp:
                    filepath.parent.mkdir(exist_ok=True, parents=True)
                    async with aiofiles.open(filepath, "wb") as w:
                        while data := await resp.content.read(IO_BUFFER):
                            if not data:
                                break
                            byte = len(data)
                            size += byte
                            pbar.update(byte)
                            # pbar.set_postfix_str(file.hash.ljust(40))
                            await w.write(data)
                            hash.update(data)
                if file.hash != hash.hexdigest():
                    filepath.unlink(True)
                    raise EOFError
                await self._mount_file(file)
            except:
                pbar.update(-size)
                await self.queues.put(file)
            if cluster:
                await cluster._check_files_sync_status(
                    "下载文件中", pbar, unit.format_more_bytes
                )
        await session.close()

    async def _mount_file(self, file: BMCLAPIFile):
        buf = io.BytesIO()
        async with aiofiles.open(
            f"./cache/download/{file.hash[:2]}/{file.hash}", "rb"
        ) as r:
            buf = io.BytesIO(await r.read())
        for storage in self.storages:
            result = -1
            try:
                result = await storage.write(file.hash, buf)
            except:
                logger.error(traceback.format_exc())
            if result != file.size:
                logger.error(
                    f"An error occured whilst downloading files: unable to copy file: {file.hash} ({unit.format_bytes(file.size)}) => {file.hash} ({unit.format_bytes(result)})."
                )

        try:
            os.remove(f"./cache/download/{file.hash[:2]}/{file.hash}")
        except:
            ...

    async def download(self, storages: list["Storage"], miss: list[BMCLAPIFile]):
        with tqdm(
            desc="Downloading files",
            unit="b",
            unit_divisor=1024,
            total=sum((file.size for file in miss)),
            unit_scale=True,
        ) as pbar:

            self.storages = storages
            for file in miss:
                await self.queues.put(file)
            timers = []
            for _ in range(0, MAX_DOWNLOAD, 32):
                for __ in range(32):
                    timers.append(
                        self._download(
                            pbar,
                            aiohttp.ClientSession(
                                BASE_URL,
                                headers={
                                    "User-Agent": USER_AGENT,
                                    "Authorization": f"Bearer {await token.getToken()}",
                                },
                            ),
                        ),
                    )
            await asyncio.gather(*timers)
            # pbar.set_postfix_str(" " * 40)
        logger.info("All files have been downloaded.")


class FileStorage(Storage):
    def __init__(self, dir: Path) -> None:
        self.dir = dir
        if self.dir.is_file():
            raise FileExistsError("The path is file.")
        self.dir.mkdir(exist_ok=True, parents=True)
        self.cache: dict[str, File] = {}
        self.timer = Timer.repeat(self.clear_cache, (), CHECK_CACHE, CHECK_CACHE)

    async def get(self, hash: str) -> File:
        if hash in self.cache:
            file = self.cache[hash]
            file.last_access = time.time()
            file.cache = True
            return file
        path = Path(str(self.dir) + f"/{hash[:2]}/{hash}")
        buf = io.BytesIO()
        async with aiofiles.open(path, "rb") as r:
            while data := await r.read(IO_BUFFER):
                buf.write(data)
        file = File(path, hash, buf.tell(), time.time(), time.time())
        file.set_data(buf.getbuffer())
        self.cache[hash] = file
        file.cache = False
        return file

    async def exists(self, hash: str) -> bool:
        return os.path.exists(str(self.dir) + f"/{hash[:2]}/{hash}")

    async def get_size(self, hash: str) -> int:
        return os.path.getsize(str(self.dir) + f"/{hash[:2]}/{hash}")

    async def copy(self, origin: Path, hash: str):
        Path(str(self.dir) + f"/{hash[:2]}/{hash}").parent.mkdir(
            exist_ok=True, parents=True
        )
        async with (
            aiofiles.open(str(self.dir) + f"/{hash[:2]}/{hash}", "wb") as w,
            aiofiles.open(origin, "rb") as r,
        ):
            await w.write(await r.read())
            return origin.stat().st_size

    async def write(self, hash: str, io: io.BytesIO) -> int:
        Path(str(self.dir) + f"/{hash[:2]}/{hash}").parent.mkdir(
            exist_ok=True, parents=True
        )
        async with aiofiles.open(str(self.dir) + f"/{hash[:2]}/{hash}", "wb") as w:
            await w.write(io.getbuffer())
            return len(io.getbuffer())

    async def check_missing_files(self, pbar, files: list[BMCLAPIFile]):
        miss = []
        for file in files:
            filepath = str(self.dir) + f"/{file.hash[:2]}/{file.hash}"
            if not os.path.exists(filepath) or os.path.getsize(filepath) != file.size:
                miss.append(file)
            pbar.update(1)
            # pbar.set_postfix_str(file.hash.ljust(40))
            await asyncio.sleep(0)
        return miss

    async def _get_missing_file(
        self, queue: asyncio.Queue[BMCLAPIFile], miss: list[BMCLAPIFile], pbar: tqdm
    ):
        while not queue.empty():
            file = await queue.get()
            filepath = str(self.dir) + f"/{file.hash[:2]}/{file.hash}"
            if not os.path.exists(filepath) or os.path.getsize(filepath) != file.size:
                miss.append(file)
            pbar.update(1)
            await asyncio.sleep(0)

    async def clear_cache(self):
        size: int = 0
        old_keys: list[str] = []
        old_size: int = 0
        for file in sorted(
            self.cache.items(), key=lambda x: x[1].last_access, reverse=True
        ):
            if size <= CACHE_BUFFER and time.time() - file[1].last_access <= CACHE_TIME:
                continue
            old_keys.append(file[0])
            old_size += file[1].size
        if not old_keys:
            return
        for key in old_keys:
            self.cache.pop(key)
        logger.info(
            f"Outdated caches: {unit.format_number(len(old_keys))}({unit.format_bytes(old_size)})."
        )

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

    async def get_cache_stats(self) -> StatsCache:
        stat = StatsCache()
        for file in self.cache.values():
            stat.total += 1
            stat.bytes += file.size
        return stat


class WebDav(Storage):
    def __init__(self) -> None:
        super().__init__()


class Cluster:
    def __init__(self) -> None:
        self.sio = socketio.AsyncClient()
        self.storages: list[Storage] = []
        self.storage_stats: dict[Storage, stats.StorageStats] = {}
        self.started = False
        self.sio.on("message", self._message)
        self.cur_storage: Optional[stats.SyncStorage] = None
        self.keepaliveTimer: Optional[Task] = None
        self.keepaliveTimeoutTimer: Optional[Task] = None
        self.keepalive_lock = asyncio.Lock()
        self.connected = False
        self.check_files_timer: Optional[Task] = None
        self.trusted = True

    def _message(self, message):
        logger.info(f"[Remote] {message}")
        if "信任度过低" in message:
            self.trusted = False

    def get_storages(self):
        return self.storages.copy()

    def add_storage(self, storage):
        self.storages.append(storage)
        type = "Unknown"
        key = time.time()
        if isinstance(storage, FileStorage):
            type = "File"
            key = storage.dir
        self.storage_stats[storage] = stats.get_storage(f"{type}_{key}")

    async def _check_files_sync_status(
        self, text: str, pbar: tqdm, format=unit.format_numbers
    ):
        if self.check_files_timer:
            return
        n, total = format(pbar.n, pbar.total)
        await dashboard.set_status(f"{text} ({n}/{total})")

    async def check_files(self):
        downloader = FileDownloader()
        files = await downloader.get_files()
        sorted(files, key=lambda x: x.hash)
        with tqdm(
            total=len(files) * len(self.storages), unit=" file(s)", unit_scale=True
        ) as pbar:
            pbar.set_description(f"[Storage] Checking files")
            task = Timer.repeat(
                self._check_files_sync_status,
                (
                    "检查文件完整性",
                    pbar,
                ),
                0,
                1,
            )
            miss_storage: list[list[BMCLAPIFile]] = await asyncio.gather(
                *[storage.check_missing_files(pbar, files) for storage in self.storages]
            )
            task.block()
            missing_files_by_storage: dict[Storage, set[BMCLAPIFile]] = {}
            total_missing_bytes = 0

            for storage, missing_files in zip(self.storages, miss_storage):
                missing_files_by_storage[storage] = set(missing_files)
                total_missing_bytes += sum(
                    (file.size for file in missing_files_by_storage[storage])
                )
            await self._check_files_sync_status("检查文件完整性", pbar)
        more_files = {storage: [] for storage in self.storages}
        prefix_files = {
            prefix: [] for prefix in (prefix.to_bytes().hex() for prefix in range(256))
        }
        prefix_hash = {
            prefix: [] for prefix in (prefix.to_bytes().hex() for prefix in range(256))
        }

        for file in files:
            prefix_files[file.hash[:2]].append(file)
            prefix_hash[file.hash[:2]].append(file.hash)
        for more, more_storage in more_files.items():
            for prefix, filelist in prefix_files.items():
                size = await more.get_files_size(prefix)
                if size != sum((file.size for file in filelist)):
                    for file in await more.get_files(prefix):
                        if file in prefix_hash[prefix]:
                            continue
                        more_storage.append(file)
        more_total = sum(len(storage) for storage in more_files.values())
        if more_total != 0:
            with tqdm(
                total=more_total, desc="Delete old files", unit="file", unit_scale=True
            ) as pbar:
                for storage, filelist in more_files.items():
                    removed = await storage.removes(filelist)
                    if removed != (total := len(filelist)):
                        logger.warn(
                            f"Unable to delete all files! Success: {removed}, Total: {total}"
                        )
                    pbar.update(total)
        if total_missing_bytes != 0 and len(miss_storage) >= 2:
            with tqdm(
                total=total_missing_bytes,
                desc="Copying local storage files",
                unit="bytes",
                unit_divisor=1024,
                unit_scale=True,
            ) as pbar:
                task = Timer.repeat(
                    self._check_files_sync_status,
                    (
                        "复制缺失文件中",
                        pbar,
                    ),
                    0,
                    1,
                )
                for storage, files in missing_files_by_storage.items():
                    for file in files:
                        for other_storage in self.storages:
                            if other_storage == storage:
                                continue
                            if (
                                await other_storage.exists(file.hash)
                                and await other_storage.get_size(file.hash) == file.size
                            ):
                                size = await storage.write(
                                    file.hash,
                                    (await other_storage.get(file.hash)).get_data(),
                                )
                                if size == -1:
                                    logger.warn(
                                        f"Failed to copy file: {file.hash}({unit.format_bytes(file.size)}) => {file.hash}({unit.format_bytes(size)})"
                                    )
                                else:
                                    missing_files_by_storage[storage].remove(file)
                                    pbar.update(size)
                await self._check_files_sync_status("复制缺失文件中", pbar)
                task.block()
        miss = set().union(*missing_files_by_storage.values())
        if not miss:
            logger.info(f"Checked all files, total: {len(files) * len(self.storages)}!")
        else:
            logger.info(
                f"Total number of missing files: {unit.format_number(len(miss))}."
            )
            await downloader.download(self.storages, list(miss))
        if os.path.exists("./cache/download"):
            paths = []
            dir = []
            for root, dirs, files in os.walk("./cache/download"):
                for file in files:
                    paths.append(os.path.join(root, file))
                if dirs:
                    for d in dirs:
                        dir.append(d)
            with tqdm(
                desc="Clean cache files",
                total=len(paths) + len(dir),
                unit="file",
                unit_scale=True,
            ) as pbar:
                if paths:
                    for path in paths:
                        os.remove(path)
                        pbar.update(1)
                if dir:
                    for d in dir:
                        os.removedirs(f"./cache/download/{d}")
                        pbar.update(1)
        if self.check_files_timer:
            self.check_files_timer.block()
        self.check_files_timer = Timer.repeat(self.check_files, (), 1800, 1800)

    async def start(
        self,
    ):
        if self.started:
            return
        logger.info(f"Starting cluster version {VERSION}.")
        await dashboard.set_status("启动节点中")
        try:
            await self.sio.connect(
                BASE_URL,
                auth={"token": await token.getToken()},
                transports=["websocket"],
            )
        except:
            logger.warn("Failed to connect to the main server. Retrying after 5s.")
            Timer.delay(self.start, (), 5)
        await dashboard.set_status("请求证书")
        await self.cert()
        await dashboard.set_status("检查文件完整性")
        await self.check_files()
        await dashboard.set_status("启动服务")
        await self.enable()
    async def get(self, hash, offset: int = 0) -> File:
        storage = self.storages[0]
        stat = self.storage_stats[storage]
        file = await storage.get(hash)
        stat.hit(file, offset)
        return file

    async def get_cache_stats(self) -> StatsCache:
        stat = StatsCache()
        for storage in self.storages:
            t = await storage.get_cache_stats()
            stat.total += t.total
            stat.bytes += t.bytes
        return stat

    async def exists(self, hash):
        return await self.storages[0].exists(hash)

    async def enable(self) -> None:
        storages = {"file": 0, "webdav": 0}
        self.trusted = True
        for storage in self.storages:
            if isinstance(storage, FileStorage):
                storages["file"] += 1
        await self.emit(
            "enable",
            {
                "host": PUBLIC_HOST,
                "port": PUBLIC_PORT or PORT,
                "version": VERSION,
                "byoc": BYOC,
                "noFastEnable": False,
                "flavor": {
                    "runtime": f"python/{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                    "storage": "+".join(
                        sorted((key for key, value in storages.items() if value))
                    ),
                },
            },
        )
        await dashboard.set_status("巡检中")
    async def message(self, type, data: list[Any]):
        if len(data) == 1:
            data.append(None)
        err, ack = data
        if type == "request-cert":
            err, ack = data
            if err:
                logger.error(f"Unable to request cert. {ack}.")
                return
            logger.info("Requested cert!")
            certificate.load_text(ack["cert"], ack["key"])
        elif type == "enable":
            err, ack = data
            if err:
                logger.error(f"Unable to start service: {err['message']}.")
                await self._keepalive_timeout()
                return
            self.connected = True
            logger.info(f"Connected to the main server! Starting service...")
            logger.info(
                f"Hosting on {CLUSTER_ID}.openbmclapi.933.moe:{PUBLIC_PORT or PORT}."
            )
            await self.start_keepalive()
            await dashboard.set_status("正常工作" + ("" if self.trusted else "（节点信任度过低）"))
        elif type == "keep-alive":
            if err:
                logger.error(f"Unable to keep alive! Reconnecting...")
                await self.disable()
            if self.cur_storage:
                storage = self.cur_storage
                logger.info(
                    f"Successfully keep alive, served {unit.format_number(storage.sync_hits)}({unit.format_bytes(storage.sync_bytes)})."
                )
                storage.object.add_last_hits(storage.sync_hits)
                storage.object.add_last_bytes(storage.sync_bytes)
                self.cur_storage = None
                if self.keepalive_lock.locked():
                    self.keepalive_lock.release()
        if type != "request-cert":
            logger.debug(type, data)

    async def start_keepalive(self, delay=0):
        if self.keepaliveTimer:
            self.keepaliveTimer.block()
        if self.keepaliveTimeoutTimer:
            self.keepaliveTimeoutTimer.block()
        self.keepaliveTimer = Timer.delay(self._keepalive, (), delay)
        self.keepaliveTimeoutTimer = Timer.delay(
            self._keepalive_timeout, (), delay + 300
        )

    async def _keepalive(self):
        for storage in stats.storages.values():
            if not self.connected:
                return
            await self.keepalive_lock.acquire()
            if not self.connected:
                return
            self.cur_storage = stats.SyncStorage(
                storage.get_total_hits() - storage.get_last_hits(),
                storage.get_total_bytes() - storage.get_last_bytes(),
                storage,
            )
            await self.emit(
                "keep-alive",
                {
                    "time": int(time.time() * 1000),
                    "hits": storage.get_total_hits() - storage.get_last_hits(),
                    "bytes": storage.get_total_bytes() - storage.get_last_bytes(),
                },
            )
        await self.start_keepalive(300)

    async def reconnect(self):
        try:
            await self.disable()
        except:
            ...
        await self.cert()
        await self.enable()

    async def _keepalive_timeout(self):
        logger.warn("Failed to keepalive! Reconnecting the main server...")
        await self.reconnect()

    async def cert(self):
        if Path("./.ssl/cert").exists() == Path("./.ssl/key").exists() == True:
            return
        await self.emit("request-cert")

    async def emit(self, channel, data=None):
        await self.sio.emit(
            channel, data, callback=lambda x: Timer.delay(self.message, (channel, x))
        )

    async def disable(self):
        self.connected = False
        if self.keepalive_lock and self.keepalive_lock.locked():
            self.keepalive_lock.release()
        if self.keepaliveTimer:
            self.keepaliveTimer.block()
        if self.keepaliveTimeoutTimer:
            self.keepaliveTimeoutTimer.block()
        if self.sio.connected:
            await self.emit("disable")
            logger.info("Disconnected from the main server...")


token = TokenManager()
cluster: Optional[Cluster] = None
last_status: str = "-"

async def init():
    global cluster
    cluster = Cluster()
    system.init()
    plugins.load_plugins()
    for plugin in plugins.get_plugins():
        await plugin.init()
        await plugin.enable()
    cluster.add_storage(FileStorage(Path("bmclapi")))
    Timer.delay(cluster.start)
    app = web.app

    @app.get("/measure/{size}")
    async def _(request: web.Request, size: int):
        if not SIGN_SKIP and not utils.check_sign(
            request.get_url(),
            CLUSTER_SECERT,
            request.get_url_params().get("s") or "",
            request.get_url_params().get("e") or "",
        ):
            yield web.Response(status_code=403)
            return
        for _ in range(size):
            yield b"\x00" * 1024 * 1024

        return

    @app.get("/download/{hash}")
    async def _(request: web.Request, hash: str):
        if (
            not SIGN_SKIP
            and not utils.check_sign(
                hash,
                CLUSTER_SECERT,
                request.get_url_params().get("s") or "",
                request.get_url_params().get("e") or "",
            )
            or not cluster
        ):
            return web.Response(status_code=403)
        if not await cluster.exists(hash):
            return web.Response(status_code=404)
        start_bytes = 0
        range_str = await request.get_headers('range', '')
        range_match = re.search(r'bytes=(\d+)-(\d+)', range_str, re.S) or re.search(r'bytes=(\d+)-', range_str, re.S)
        if range_match:
            start_bytes = int(range_match.group(1)) if range_match else 0
        data = await cluster.get(hash, start_bytes)
        if data.is_url() and isinstance(data.get_path(), str):
            return web.RedirectResponse(str(data.get_path()))
        return data.get_data()

    router: web.Router = web.Router("/bmcl")
    dir = Path("./bmclapi_dashboard/")
    dir.mkdir(exist_ok=True, parents=True)
    app.mount_resource(web.Resource("/bmcl", dir, show_dir=False))

    @router.websocket("/")
    async def _(request: web.Request, ws: web.WebSocket):
        auth = False
        for cookie in await request.get_cookies():
            if cookie.name == "auth" and dashboard.token_isvaild(cookie.value):
                await ws.send(dashboard.to_bytes("auth", DASHBOARD_USERNAME).io.getbuffer())
                auth = True
                break
        if not auth:
            await ws.send(dashboard.to_bytes("auth", None).io.getbuffer())
        async for raw_data in ws:
            if isinstance(raw_data, str):
                return
            if isinstance(raw_data, io.BytesIO):
                raw_data = raw_data.getvalue()
            input = utils.DataInputStream(raw_data)
            type = input.readString()
            data = dashboard.deserialize(input)
            await ws.send(dashboard.to_bytes(type, await dashboard.process(type, data)).io.getbuffer())
    @router.get("/auth")
    async def _(request: web.Request):
        auth = (await request.get_headers("Authorization")).split(" ", 1)[1]
        try:
            info = json.loads(base64.b64decode(auth))
        except:
            return web.Response(status_code=401)
        if info["username"] != DASHBOARD_USERNAME or info["password"] != DASHBOARD_PASSWORD:
            return web.Response(status_code=401)
        token = dashboard.generate_token(request)
        return web.Response(DASHBOARD_USERNAME, cookies=[web.Cookie("auth", token.value, expires=int(time.time() + 86400))])

    app.mount(router)
    app.redirect("/bmcl", "/bmcl/")


async def close():
    global cluster
    for plugin in plugins.get_enable_plugins():
        await plugin.disable()
    if cluster:
        await cluster.disable()
