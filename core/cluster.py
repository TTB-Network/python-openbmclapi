import asyncio
from dataclasses import dataclass
import hashlib
import hmac
import io
import os
from pathlib import Path
import urllib.parse as urlparse
import sys
import time
import traceback
import aiofiles
import aiohttp
from typing import Any, Optional
import socketio
from tqdm import tqdm
from config import Config
from core import unit
from core.timer import Task, Timer  # type: ignore
import pyzstd as zstd
import core.utils as utils
import core.stats as stats
import core.web as web
from core.logger import logger

from core.api import (
    File,
    BMCLAPIFile,
    Storage,
    get_hash,
)

VERSION = "1.9.8"
API_VERSION = "1.9.8"
USER_AGENT = f"openbmclapi-cluster/{API_VERSION} python-openbmclapi/{VERSION}"
BASE_URL = "https://openbmclapi.bangbang93.com/"
CLUSTER_ID: str = Config.get("cluster_id") # type: ignore
CLUSTER_SECERT: str = Config.get("cluster_secret") # type: ignore
IO_BUFFER: int = Config.get("io_buffer") # type: ignore
MAX_DOWNLOAD: int = max(1, Config.get("max_download")) # type: ignore
BYOC: bool = Config.get("byoc") # type: ignore
PUBLIC_HOST: str = Config.get("public_host") # type: ignore
PUBLIC_PORT: int = Config.get("public_port") # type: ignore
PORT: int = Config.get("port") # type: ignore
CACHE_BUFFER: int = 1024 * 1024 * 512
CACHE_TIME: int = 1800
CHECK_CACHE: int = 60
SIGN_SKIP: bool = False

class TokenManager:
    def __init__(self) -> None:
        self.token = None

    async def fetchToken(self):
        async with aiohttp.ClientSession(
            headers={"User-Agent": USER_AGENT}, base_url=BASE_URL
        ) as session:
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

            except aiohttp.ClientError as e:
                logger.error(f"Error fetching token: {e}.")

    async def getToken(self) -> str:
        if not self.token:
            await self.fetchToken()
        return self.token or ""

class ParseFileList:
    def __init__(self, data) -> None:
        self.data = io.BytesIO(data)
        self.files = []
        for _ in range(self.read_long()):
            self.files.append(BMCLAPIFile(self.read_string(), self.read_string(), self.read_long()))
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
        return self.data.read(self.read_long()).decode('utf-8')
class FileDownloader:
    def __init__(self) -> None:
        self.files = []
        self.queues: asyncio.Queue[BMCLAPIFile] = asyncio.Queue()
        self.storages = []
    async def get_files(self):
        async with aiohttp.ClientSession(base_url=BASE_URL, headers={
            "User-Agent": USER_AGENT,
            "Authorization": f"Bearer {await token.getToken()}"
        }) as session:
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
        await session.close()

    async def _mount_file(self, file: BMCLAPIFile):
        buf = io.BytesIO()
        async with aiofiles.open(f"./cache/download/{file.hash[:2]}/{file.hash}", "rb") as r:
            buf = io.BytesIO(await r.read())
        for storage in self.storages:
            result = -1
            try:
                result = await storage.write(file.hash, buf)
            except:
                logger.error(traceback.format_exc())
            if result != file.size:
                logger.error(f"Download file error: File {file.hash}({unit.format_bytes(file.size)}) copy to target file error: {file.hash}({unit.format_bytes(result)})")
        os.remove(f"./cache/download/{file.hash[:2]}/{file.hash}")
    async def download(self, storages: list['Storage'], miss: list[BMCLAPIFile]):
        with tqdm(desc="Downloading files", unit="bit", total=sum((file.size for file in miss)), unit_scale=True) as pbar:
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
        logger.info("Files downloaded.")
class FileStorage(Storage):
    def __init__(self, dir: Path) -> None:
        self.dir = dir
        if self.dir.is_file():
            raise FileExistsError("The path is file.")
        self.dir.mkdir(exist_ok=True, parents=True)
        self.cache: dict[str, File] = {}
        self.stats: stats.StorageStats = stats.get_storage(f"File_{self.dir}")
        self.timer = Timer.repeat(self.clear_cache, (), CHECK_CACHE, CHECK_CACHE)
    async def get(self, hash: str) -> File:
        if hash in self.cache:
            file = self.cache[hash]
            file.last_access = time.time()
            self.stats.hit(file, cache = True)
            return file
        path = Path(str(self.dir) + f"/{hash[:2]}/{hash}")
        buf = io.BytesIO()
        async with aiofiles.open(path, "rb") as r:
            while data := await r.read(IO_BUFFER):
                buf.write(data)
        file = File(path, hash, buf.tell(), time.time(), time.time())
        file.set_data(buf.getbuffer())
        self.cache[hash] = file
        self.stats.hit(file)
        return file
    async def exists(self, hash: str) -> bool:
        return os.path.exists(str(self.dir) + f"/{hash[:2]}/{hash}")
    async def get_size(self, hash: str) -> int:
        return os.path.getsize(str(self.dir) + f"/{hash[:2]}/{hash}")
    async def write(self, hash: str, io: io.BytesIO) -> int:
        Path(str(self.dir) + f"/{hash[:2]}/{hash}").parent.mkdir(exist_ok=True, parents=True)
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
    async def _get_missing_file(self, queue: asyncio.Queue[BMCLAPIFile], miss: list[BMCLAPIFile], pbar: tqdm):
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
        for file in sorted(self.cache.items(), key=lambda x: x[1].last_access, reverse=True):
            if size <= CACHE_BUFFER and time.time() - file[1].last_access <= CACHE_TIME:
                continue
            old_keys.append(file[0])
            old_size += file[1].size
        if not old_keys:
            return
        for key in old_keys:
            self.cache.pop(key)
        logger.info(f"Outdate caches: {unit.format_number(len(old_keys))}({unit.format_bytes(old_size)})")
class Cluster:
    def __init__(self) -> None:
        self.sio = socketio.AsyncClient()
        self.storages: list[Storage] = []
        self.started = False
        self.sio.on("message", lambda x: logger.info(f"[Remote] {x}"))
        self.cur_storage: Optional[stats.SyncStorage] = None
        self.keepaliveTimer: Optional[Task] = None
        self.keepaliveTimeoutTimer: Optional[Task] = None
        self.keepalive_lock = asyncio.Lock()
        self.connected = False
    def add_storage(self, storage):
        self.storages.append(storage)
    async def start(self, ):
        if self.started:
            return
        await self.sio.connect(BASE_URL, auth={"token": await token.getToken()}, transports=["websocket"])
        await self.cert()
        downloader = FileDownloader()
        files = await downloader.get_files()
        with tqdm(total=len(files) * len(self.storages), unit=" file(s)", unit_scale=True) as pbar:
            pbar.set_description(f"[Storage] Checking files")
            miss_storage: list[list[BMCLAPIFile]] = await asyncio.gather(*[storage.check_missing_files(pbar, files) for storage in self.storages])  
            # pbar.set_postfix_str(" " * 40)
            missing_files_by_storage: dict[Storage, set[BMCLAPIFile]] = {}  
            total_missing_bytes = 0

            for storage, missing_files in zip(self.storages, miss_storage):  
                missing_files_by_storage[storage] = set(missing_files)  
                total_missing_bytes += sum((file.size for file in missing_files_by_storage[storage]))
        if total_missing_bytes != 0 and len(miss_storage) >= 2:
            with tqdm(total=total_missing_bytes, desc="Copying local storage files", unit="bytes", unit_scale=True) as pbar:
                for storage, files in missing_files_by_storage.items():
                    for file in files:
                        for other_storage in self.storages:
                            if other_storage == storage:
                                continue
                            if await other_storage.exists(file.hash) and await other_storage.get_size(file.hash) == file.size:
                                size = await storage.write(file.hash, (await other_storage.get(file.hash)).get_data())
                                if size == -1:
                                    logger.warn(f"Failed to copy file: {file.hash}({unit.format_bytes(file.size)}) => {file.hash}({unit.format_bytes(size)})")
                                else:
                                    missing_files_by_storage[storage].remove(file)
                                    pbar.update(size)
                                    # pbar.set_postfix_str(file.hash.ljust(40))
                # pbar.set_postfix_str(" " * 40)
        miss = set().union(*missing_files_by_storage.values())
        if not miss:
            logger.info("Checked all files")
        else:
            logger.info(f"Storage(s) total of missing files: {unit.format_number(len(miss))}")
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
            with tqdm(desc="Clean cache files", total=len(paths) + len(dir), unit="file", unit_scale=True) as pbar:
                if paths:
                    for path in paths:
                        os.remove(path)
                        pbar.disable()
                        pbar.update(1)
                if dir:
                    for d in dir:
                        os.removedirs(f"./cache/download/{d}")
                        pbar.update(1)
        await self.enable()
    async def get(self, hash):
        return await self.storages[0].get(hash)
    async def exists(self, hash):
        return await self.storages[0].exists(hash)
    async def enable(self) -> None:
        storages = {"file": 0, "webdav": 0}
        for storage in self.storages:
            if isinstance(storage, FileStorage):
                storages["file"] += 1
        await self.emit("enable", 
            {
                "host": PUBLIC_HOST,
                "port": PUBLIC_PORT or PORT,
                "version": VERSION,
                "byoc": BYOC,
                "noFastEnable": False,
                "flavor": {
                    "runtime": f"python/{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                    "storage": "+".join(sorted((key for key, value in storages.items() if value)))
                }
            }
        )
    async def message(self, type, data: list[Any]):
        if len(data) == 1:
            data.append(None)
        err, ack = data
        if type == "request-cert":
            err, ack = data
            if err:
                logger.error(f"Error: Unable to request cert. {ack}")
                return
            logger.info("Requested cert!")
            cert_file = Path(".ssl/cert")
            key_file = Path(".ssl/key")
            for file in (cert_file, key_file):
                file.parent.mkdir(exist_ok=True, parents=True)
            with open(cert_file, "w") as w:
                w.write(ack["cert"])
            with open(key_file, "w") as w:
                w.write(ack["key"])
            web.load_cert()
            cert_file.unlink()
            key_file.unlink()
        elif type == "enable":
            err, ack = data
            if err:
                logger.error(f"Error: Unable to start service: {err['message']}")
                await self._keepalive_timeout()
                return
            self.connected = True
            logger.info("Connected Main, Starting service.")
            await self.start_keepalive()
        elif type == "keep-alive":
            if err:
                logger.error(f"Error: Unable to keep alive. Now reconnecting")
                await self.disable()
            if self.cur_storage:
                storage = self.cur_storage
                logger.info(f"Success keepalive, serve: {unit.format_number(storage.sync_hits)}({unit.format_bytes(storage.sync_bytes)})")
                storage.object.add_last_hits (storage.sync_hits)
                storage.object.add_last_bytes(storage.sync_bytes)
                self.cur_storage = None
                self.keepalive_lock.release()
        if type != "request-cert":
            logger.debug(type, data)
    async def start_keepalive(self, delay = 0):
        if self.keepaliveTimer:
            self.keepaliveTimer.block()
        if self.keepaliveTimeoutTimer:
            self.keepaliveTimeoutTimer.block()
        self.keepaliveTimer = Timer.delay(self._keepalive, (), delay)
        self.keepaliveTimeoutTimer = Timer.delay(self._keepalive_timeout, (), delay + 300)
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
                storage
            )
            await self.emit("keep-alive", {
                "time": int(time.time()),
                "hits": storage.get_total_hits() - storage.get_last_hits(),
                "bytes": storage.get_total_bytes() - storage.get_last_bytes(),
            })
        await self.start_keepalive(300)
    async def _keepalive_timeout(self):
        logger.warn("Failed to keepalive? Reconnect the main")
        try:
            await self.disable()
        except:
            ...
        await self.cert()
        await self.enable()
    async def cert(self):
        if Path(".ssl/cert").exists() == Path(".ssl/key").exists() == True:
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
            logger.info("Disconnected from Main")

class DashboardData:
    @staticmethod
    def deserialize(data: utils.DataInputStream):
        match (data.readVarInt()):
            case 0:
                return data.readString()
            case 1:
                return data.readBoolean()
            case 2:
                return int(data.readString())
            case 3:
                return float(data.readString())
            case 4:
                return [DashboardData.deserialize(data) for _ in range(data.readVarInt())]
            case 5:
                return {DashboardData.deserialize(data): DashboardData.deserialize(data) for _ in range(data.readVarInt())}
            case 6:
                return None
    @staticmethod
    def serialize(data: Any):
        buf = utils.DataOutputStream()
        if isinstance(data, str):
            buf.writeVarInt(0)
            buf.writeString(data)
        elif isinstance(data, bool):
            buf.writeVarInt(1)
            buf.writeBoolean(data)
        elif isinstance(data, float):
            buf.writeVarInt(2)
            buf.writeString(str(data))
        elif isinstance(data, int):
            buf.writeVarInt(3)
            buf.writeString(str(data))
        elif isinstance(data, list):
            buf.writeVarInt(4)
            buf.writeVarInt(len(data))
            buf.write(b''.join((DashboardData.serialize(v).io.getvalue() for v in data)))
        elif isinstance(data, dict):
            buf.writeVarInt(5)
            buf.writeVarInt(len(data.keys()))
            buf.write(b''.join((DashboardData.serialize(k).io.getvalue() + DashboardData.serialize(v).io.getvalue() for k, v in data.items())))
        elif data == None:
            buf.writeVarInt(6)
        return buf
    @staticmethod
    async def process(type: str, data: Any):
        if type == "runtime":
            return float(os.getenv("STARTUP") or 0)
        if type == "dashboard":
            return {"hourly": stats.hourly(), "days": stats.daily()}

token = TokenManager()
cluster: Optional[Cluster] = None

async def init():
    global cluster
    cluster = Cluster()
    cluster.add_storage(FileStorage(Path("bmclapi")))
    Timer.delay(cluster.start)
    app = web.app

    @app.get("/measure/{size}")
    async def _(request: web.Request, size: int):
        if not SIGN_SKIP and not utils.check_sign(request.get_url(), CLUSTER_SECERT, request.get_url_params().get("s") or "", request.get_url_params().get("e") or ""):
            yield web.Response(status_code=403)
            return
        for _ in range(size):
            yield b"\x00" * 1024 * 1024

        return 

    @app.get("/download/{hash}")
    async def _(request: web.Request, hash: str):
        if not SIGN_SKIP and not utils.check_sign(hash, CLUSTER_SECERT, request.get_url_params().get("s") or "", request.get_url_params().get("e") or "") or not cluster:
            return web.Response(status_code=403)
        if not await cluster.exists(hash):
            return web.Response(status_code=404)
        data = await cluster.get(hash)
        if data.is_url() and isinstance(data.get_path(), str):
            return web.RedirectResponse(str(data.get_path()))
        return data.get_data()

    router: web.Router = web.Router("/bmcl")
    dir = Path("./bmclapi_dashboard/")
    dir.mkdir(exist_ok=True, parents=True)
    app.mount_resource(web.Resource("/bmcl", dir, show_dir=False))

    @router.get("/")
    async def _(request: web.Request):
        return Path("./bmclapi_dashboard/index.html")

    @router.websocket("/")
    async def _(ws: web.WebSocket):
        async for raw_data in ws:
            if isinstance(raw_data, str):
                return
            if isinstance(raw_data, io.BytesIO):
                raw_data = raw_data.getvalue()
            input = utils.DataInputStream(raw_data)
            type = input.readString()
            data = DashboardData.deserialize(input)
            output = utils.DataOutputStream()
            output.writeString(type)
            output.write(DashboardData.serialize(await DashboardData.process(type, data)).io.getvalue())
            await ws.send(output.io.getvalue())

    @router.get("/master")
    async def _(request: web.Request, url: str):
        content = io.BytesIO()
        async with aiohttp.ClientSession(BASE_URL) as session:
            async with session.get(url) as resp:
                content.write(await resp.read())
        return content  # type: ignore
    app.mount(router)

async def close():
    global cluster
    if cluster:
        await cluster.disable()

"""async def clearCache():
    global cache
    data = cache.copy()
    size = 0
    for k, v in data.items():
        if v.access + 1440 < time.time():
            cache.pop(k)
        else:
            size += v.size
    if size > 1024 * 1024 * 512:
        data = cache.copy()
        for k, v in data.items():
            if size > 1024 * 1024 * 512:
                cache.pop(k)
                size -= v.size
            else:
                break
"""
