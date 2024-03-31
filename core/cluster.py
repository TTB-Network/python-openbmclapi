import asyncio
import base64
from enum import Enum
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
from typing import Any, Optional, Type
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
import aiowebdav.client as webdav3_client


from core.api import (
    File,
    BMCLAPIFile,
    FileCheckType,
    StatsCache,
    Storage,
    get_hash,
)

VERSION = ""
version_path = Path("VERSION")
if version_path.exists():
    with open(Path("VERSION"), "r", encoding="utf-8") as f:
        VERSION = f.read().split("\n")[0]
        f.close()
else:
    VERSION = "Unknown"
API_VERSION = "1.10.1"
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
SIGN_SKIP: bool = True
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
                logger.error(
                    f"An error occured whilst fetching token, retrying in 5s: {e}."
                )
                await asyncio.sleep(5)
                return self.fetchToken()

    async def getToken(self) -> str:
        if not self.token:
            await self.fetchToken()
        return self.token or ""


class ParseFileList:
    async def __call__(self, data) -> list[BMCLAPIFile]:
        self.data = io.BytesIO(data)
        self.files = []
        with tqdm(total=self.read_long(), desc="[ParseFileList]") as pbar:
            for _ in range(pbar.total):
                self.files.append(
                    BMCLAPIFile(
                        self.read_string(),
                        self.read_string(),
                        self.read_long(),
                        self.read_long(),
                    )
                )
                pbar.update(1)
        return self.files

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
        self.last_modified: int = 0

    async def get_files(self) -> list[BMCLAPIFile]:
        async with aiohttp.ClientSession(
            base_url=BASE_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {await token.getToken()}",
            },
        ) as session:
            logger.debug("Created ClientSession")
            async with session.get(
                "/openbmclapi/files",
                data={
                    "responseType": "buffer",
                    "cache": "",
                    "lastModified": self.last_modified,
                },
            ) as req:
                logger.debug(f"Filelist response status: {req.status}")
                if req.status == 204:
                    return []
                if req.status != 200:
                    try:
                        req.raise_for_status()
                    except:
                        logger.error(traceback.format_exc())
                    return []
                logger.info("Requested filelist.")
                files = await ParseFileList()(zstd.decompress(await req.read()))
                self.last_modified = max(
                    self.last_modified, *(file.mtime for file in files)
                )
                logger.debug(f"Filelist last modified: {self.last_modified}")
                return files

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
            await dashboard.set_status_by_tqdm(
                "下载文件中", pbar, unit.format_more_bytes
            )
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


class FileCheck:
    def __init__(self, downloader: FileDownloader) -> None:
        self.checked = False
        self.downloader = downloader
        self.check_type = FileCheckType.EXISTS
        self.files = []
        self.pbar: Optional[tqdm] = None
        self.check_files_timer: Optional[Task] = None

    async def __call__(
        self,
    ) -> Any:
        if not self.checked:
            await dashboard.set_status("拉取最新文件列表")
        files = await self.downloader.get_files()
        sorted(files, key=lambda x: x.hash)
        if not self.checked:
            await dashboard.set_status("正在检查缺失文件")
        if not files:
            logger.warn("File check skipped as there are currently no files available.")
            if self.check_files_timer:
                self.check_files_timer.block()
            self.check_files_timer = Timer.repeat(self, (), 1800, 1800)
            return
        with tqdm(
            total=len(files) * len(storages.get_storages()),
            unit=" file(s)",
            unit_scale=True,
        ) as pbar:
            self.pbar = pbar
            self.files = files
            await dashboard.set_status_by_tqdm("文件完整性", pbar)
            pbar.set_description(f"[Storage] Checking files")

            miss_storage: list[list[BMCLAPIFile]] = await asyncio.gather(
                *[
                    self.check_missing_files(storage)
                    for storage in storages.get_storages()
                ]
            )
            missing_files_by_storage: dict[Storage, set[BMCLAPIFile]] = {}
            total_missing_bytes = 0

            for storage, missing_files in zip(storages.get_storages(), miss_storage):
                missing_files_by_storage[storage] = set(missing_files)
                total_missing_bytes += sum(
                    (file.size for file in missing_files_by_storage[storage])
                )

            self.pbar = None
        if not self.checked:
            self.checked = True
            more_files = {storage: [] for storage in storages.get_storages()}
            prefix_files = {
                prefix: []
                for prefix in (prefix.to_bytes(1, "big").hex() for prefix in range(256))
            }
            prefix_hash = {
                prefix: []
                for prefix in (prefix.to_bytes(1, "big").hex() for prefix in range(256))
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
                    total=more_total,
                    desc="Delete old files",
                    unit="file",
                    unit_scale=True,
                ) as pbar:
                    await dashboard.set_status_by_tqdm("删除旧文件中", pbar)
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
                    await dashboard.set_status_by_tqdm("复制缺失文件中", pbar)
                    for storage, files in missing_files_by_storage.items():
                        for file in files:
                            for other_storage in storages.get_storages():
                                if other_storage == storage:
                                    continue
                                if (
                                    await other_storage.exists(file.hash)
                                    and await other_storage.get_size(file.hash)
                                    == file.size
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
        miss = set().union(*missing_files_by_storage.values())
        if not miss:
            logger.info(
                f"Checked all files, total: {len(files) * len(storages.get_storages())}!"
            )
        else:
            logger.info(
                f"Total number of missing files: {unit.format_number(len(miss))}."
            )
            await self.downloader.download(storages.get_storages(), list(miss))
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
                await dashboard.set_status_by_tqdm("清理缓存文件中", pbar)
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
        self.check_files_timer = Timer.repeat(self, (), 1800, 1800)

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

    async def check_missing_files(self, storage: Storage):
        if not self.pbar:
            raise
        miss = []
        handler = None
        if self.check_type == FileCheckType.EXISTS:
            handler = self._exists
        if self.check_type == FileCheckType.SIZE:
            handler = self._size
        if self.check_type == FileCheckType.HASH:
            handler = self._hash
        if handler is None:
            raise KeyError(f"Not found handler {self.check_type}")
        for file in self.files:
            if not await handler(file, storage):
                miss.append(file)
            self.pbar.update(1)
            await asyncio.sleep(0)
        return miss


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

    async def get_hash(self, hash: str) -> str:
        h = get_hash(hash)
        async with aiofiles.open(str(self.dir) + f"/{hash[:2]}/{hash}", "rb") as r:
            while data := await r.read(Config.get("advanced.io_buffer")):
                if not data:
                    break
                h.update(data)
                await asyncio.sleep(0.001)
        return h.hexdigest()

    async def clear_cache(self):
        size: int = 0
        old_keys: list[str] = []
        old_size: int = 0
        file: File
        key: str
        for key, file in sorted(
            self.cache.items(), key=lambda x: x[1].expiry, reverse=True
        ):
            if size <= CACHE_BUFFER and file.last_access + CACHE_TIME <= time.time():
                continue
            old_keys.append(key)
            old_size += file.size
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
    def __init__(
        self,
        username: str,
        password: str,
        hostname: str,
        endpoint: str,
        token: Optional[str] = None,
    ) -> None:
        self.username = username
        self.password = password
        self.hostname = hostname
        self.endpoint = endpoint
        self.files: dict[str, File] = {}
        self.token = token
        self.fetch = False
        self.cache: dict[str, File] = {}
        self.empty = File("", "", 0)
        self.lock = None
        Timer.delay(self._list_all)

    def _endpoint(self, file: str):
        return f"{self.endpoint}/{file.removeprefix('/')}"

    def _client(self):
        token = {}
        if self.token != None:
            token["webdav_token"] = self.token
        return webdav3_client.Client(
            {
                "webdav_username": self.username,
                "webdav_password": self.password,
                "webdav_hostname": self.hostname,
                **token
            }
        )

    async def get(self, file: str) -> File:
        await self._wait_lock()
        if file in self.cache and self.cache[file].expiry - 10 > time.time():
            self.cache[file].cache = True
            self.cache[file].last_hit = time.time()
            return self.cache[file]
        async with aiohttp.ClientSession(
            auth=aiohttp.BasicAuth(self.username, self.password)
        ) as session:
            async with session.get(
                self.hostname + self._endpoint(file[:2] + "/" + file), allow_redirects=False
            ) as resp:
                f = File(
                    self.hostname + self._endpoint(file[:2] + "/" + file),
                    file,
                    size=int(resp.headers.get("Content-Length", 0)),
                )
                if resp.status == 200:
                    f.set_data(await resp.read())
                elif resp.status // 100 == 3:
                    f.path = resp.headers.get("Location")
                self.cache[file] = f
        return self.cache[file]

    async def _list_all(self, force=False):
        if self.fetch and not force:
            return
        if not self.fetch:
            self.lock = asyncio.get_running_loop().create_future()
        self.fetch = True
        async with self._client() as client:
            dirs = (await client.list(self.endpoint))[1:]
            with tqdm(total=len(dirs), desc=f"[WebDav List Files <endpoint: '{self.endpoint}'>]") as pbar:
                await dashboard.set_status_by_tqdm("正在获取 WebDav 文件列表中", pbar)
                for dir in (await client.list(self.endpoint))[1:]:
                    pbar.update(1)
                    files: dict[str, File] = {}
                    for file in (
                        await client.list(
                            self._endpoint(
                                dir,
                            ),
                            get_info=True,
                        )
                    )[1:]:
                        files[file["name"]] = File(
                            file["path"].removeprefix(f"/dav/{self.endpoint}/"),
                            file["name"],
                            int(file["size"]),
                        )
                        await asyncio.sleep(0)
                    for remove in set(file for file in self.files.keys() if file.startswith(dir)) - set(files.keys()):
                        self.files.pop(remove)
                    self.files.update(files)
        if self.lock != None:
            self.lock.cancel()
        return self.files

    async def _wait_lock(self):
        if self.lock:
            await asyncio.wait_for(self.lock, timeout = None)

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
        async with self._client() as client:
            path = self._endpoint(f"{hash[:2]}/{hash}")
            await client.upload_to(io, path)
            self.files[hash] = File(path, hash, len(io.getbuffer()))
            return self.files[hash].size

    async def get_files(self, dir: str) -> list[str]:
        await self._wait_lock()
        return list((hash for hash in self.files.keys() if hash.startswith(dir)))

    async def get_hash(self, hash: str) -> str:
        async with self._client() as session:
            h = get_hash(hash)
            async for data in await session.download_iter(
                self._endpoint(f"{hash[:2]}/{hash}")
            ):
                h.update(data)
            return h.hexdigest()

    async def get_files_size(self, dir: str) -> int:
        await self._wait_lock()
        return sum(
            (file.size for hash, file in self.files.items() if hash.startswith(dir))
        )

    async def removes(self, hashs: list[str]) -> int:
        success = 0
        async with self._client() as client:
            for hash in hashs:
                await client.clean(self._endpoint(f"{hash[:2]}/{hash}"))
                success += 1
        return success

    async def get_cache_stats(self) -> StatsCache:
        return StatsCache()


class TypeStorage(Enum):
    FILE = "file"
    WEBDAV = "webdav"


class StorageManager:
    def __init__(self) -> None:
        self._storages: list[Storage] = []
        self._interface_storage: dict[TypeStorage, Type[Storage]] = {}
        self._storage_stats: dict[Storage, stats.StorageStats] = {}

    def add_storage(self, storage):
        self._storages.append(storage)
        type = "Unknown"
        key = time.time()
        if isinstance(storage, FileStorage):
            type = "File"
            key = storage.dir
        self._storage_stats[storage] = stats.get_storage(f"{type}_{key}")

    def remove_storage(self, storage):
        self._storages.remove(storage)

    def add_interface(self, type: TypeStorage, storage: Type[Storage]):
        self._interface_storage[type] = storage

    def create_storage(self, type: TypeStorage, *args, **kwargs):
        self.add_storage(self._interface_storage[type](*args, **kwargs))

    def get_storages(self):
        return self._storages

    def get_storage_stats(self):
        return self._storage_stats

    async def get(self, hash: str, offset: int) -> File:
        storage = self.get_storages()[0]
        file = await storage.get(hash)
        self._storage_stats[storage].hit(file, offset)
        return file

    async def exists(self, hash: str) -> bool:
        return await self.get_storages()[0].exists(hash)

    def get_storage_stat(self, storage):
        return self._storage_stats[storage]


class Cluster:
    def __init__(self) -> None:
        self.connected = False
        self.sio = socketio.AsyncClient()
        self.sio.on("message", self._message)
        self.stats_storage: Optional[stats.SyncStorage] = None
        self.downloader = FileDownloader()
        self.file_check = FileCheck(self.downloader)
        self._enable_timer: Optional[Task] = None
        self.keepaliveTimer: Optional[Task] = None
        self.keepaliveTimeoutTimer: Optional[Task] = None
        self.keepalive_lock = asyncio.Lock()

    def _message(self, message):
        logger.info(f"[Remote] {message}")
        if "信任度过低" in message:
            self.trusted = False

    async def emit(self, channel, data=None):
        await self.sio.emit(
            channel, data, callback=lambda x: Timer.delay(self.message, (channel, x))
        )

    async def init(self):
        if not self.sio.connected:
            try:
                await self.sio.connect(
                    BASE_URL,
                    auth={"token": await token.getToken()},
                    transports=["websocket"],
                )
            except:
                logger.warn("Failed to connect to the main server, retrying after 5s.")
                Timer.delay(self.init, (), 5)
                return
        await self.start()

    async def start(self):
        await self.cert()
        if len(storages.get_storages()) == 0:
            logger.warn("There is currently no Storage, the enabled nodes are blocked.")
            return
        await self.start_storage()

    async def start_storage(self):
        if len(storages.get_storages()) == 0:
            if self.connected:
                self.disable()
            logger.warn("There is currently no Storage, the enabled nodes are blocked.")
            return
        await self.file_check()
        if not self.connected:
            await self.enable()


    async def cert(self):
        await self.emit("request-cert")

    async def enable(self):
        if self.connected:
            logger.debug(
                "Still trying to enable cluster? You has been blocked. (\nFrom bangbang93:\n 谁他妈\n 一秒钟发了好几百个enable请求\n ban了解一下等我回杭州再看\n ban了先\n\n > Timestamp at 2024/3/30 14:07 GMT+8\n)"
            )
            return
        self.connected = True
        if self._enable_timer != None:
            self._enable_timer.block()
        self._enable_timer = Timer.delay(self.reconnect, (), 30)
        await self._enable()

    async def reconnect(self):
        if self.connected:
            await self.disable()
            self.connected = False
            logger.info("Retrying after 5s.")
            await asyncio.sleep(5)
        await self.enable()

    async def _enable(self):
        storage_str = {"file": 0, "webdav": 0}
        self.trusted = True
        for storage in storages.get_storages():
            if isinstance(storage, FileStorage):
                storage_str["file"] += 1
            elif isinstance(storage, WebDav):
                storage_str["webdav"] += 1
        await self.emit(
            "enable",
            {
                "host": PUBLIC_HOST,
                "port": PUBLIC_PORT or PORT,
                "version": API_VERSION,
                "byoc": BYOC,
                "noFastEnable": False,
                "flavor": {
                    "runtime": f"python/{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                    "storage": "+".join(
                        sorted((key for key, value in storage_str.items() if value))
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
            logger.success("Requested cert!")
            certificate.load_text(ack["cert"], ack["key"])
        elif type == "enable":
            err, ack = data
            if self._enable_timer != None:
                self._enable_timer.block()
                self._enable_timer = None
            if err:
                logger.error(
                    f"Unable to start service: {err['message']} Retry in 5s to reconnect."
                )
                await asyncio.sleep(5)
                await self.reconnect()
                return
            self.connected = True
            logger.success(f"Connected to the main server! Starting service...")
            logger.info(
                f"Hosting on {CLUSTER_ID}.openbmclapi.933.moe:{PUBLIC_PORT or PORT}."
            )
            await self.start_keepalive()
            await dashboard.set_status(
                "正常工作" + ("" if self.trusted else "（节点信任度过低）")
            )
        elif type == "keep-alive":
            if err:
                logger.error(f"Unable to keep alive! Reconnecting...")
                await self.reconnect()
                return
            if self.cur_storage:
                storage = self.cur_storage
                logger.success(
                    f"Successfully keep alive, serving {unit.format_number(storage.sync_hits)}({unit.format_bytes(storage.sync_bytes)})."
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
        await self.start_keepalive(60)

    async def _keepalive_timeout(self):
        logger.warn("Failed to keepalive! Reconnecting the main server...")
        await self.reconnect()

    async def disable(self):
        if self.sio.connected:
            await self.emit("disable")
            logger.info("Disconnected from the main server...")
        await dashboard.set_status("已下线")

    async def get_cache_stats(self) -> StatsCache:
        stat = StatsCache()
        for storage in storages.get_storages():
            t = await storage.get_cache_stats()
            stat.total += t.total
            stat.bytes += t.bytes
        return stat


token = TokenManager()
cluster: Optional[Cluster] = None
last_status: str = "-"
storages = StorageManager()
github_api = "https://api.github.com"
download_url = ""


async def check_update():
    global fetched_version
    fetched_version = "Unknown"
    async with aiohttp.ClientSession(base_url=github_api) as session:
        logger.info("Checking update...")
        try:
            async with session.get(
                "/repos/TTB-Network/python-openbmclapi/releases/latest"
            ) as req:
                req.raise_for_status()
                data = await req.json()
                fetched_version = data["tag_name"]
            if fetched_version != VERSION:
                logger.success(f"New version found: {fetched_version}!")
                await dashboard.trigger("version")
            else:
                logger.info(f"Already up to date.")
        except aiohttp.ClientError as e:
            logger.error(f"An error occured whilst checking update: {e}.")
    Timer.delay(check_update, (), 3600)


async def init():
    await check_update()
    global cluster
    cluster = Cluster()
    system.init()
    plugins.load_plugins()
    for plugin in plugins.get_plugins():
        await plugin.init()
        await plugin.enable()
    storages.add_storage(FileStorage(Path("bmclapi")))
    Timer.delay(cluster.init)
    app = web.app

    @app.get("/measure/{size}")
    async def _(request: web.Request, size: int, config: web.ResponseConfiguration):
        if not SIGN_SKIP and not utils.check_sign(
            request.get_url(),
            CLUSTER_SECERT,
            request.get_url_params().get("s") or "",
            request.get_url_params().get("e") or "",
        ):
            yield web.Response(status_code=403)
            return
        config.length = size * 1024 * 1024
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
        if not await storages.exists(hash):
            return web.Response(status_code=404)
        start_bytes = 0
        range_str = await request.get_headers("range", "")
        range_match = re.search(r"bytes=(\d+)-(\d+)", range_str, re.S) or re.search(
            r"bytes=(\d+)-", range_str, re.S
        )
        if range_match:
            start_bytes = int(range_match.group(1)) if range_match else 0
        data = await storages.get(hash, start_bytes)
        if data.is_url() and isinstance(data.get_path(), str):
            return web.RedirectResponse(str(data.get_path()))
        return data.get_data()

    router: web.Router = web.Router("/bmcl")
    dir = Path("./bmclapi_dashboard/")
    dir.mkdir(exist_ok=True, parents=True)
    app.mount_resource(web.Resource("/bmcl", dir, show_dir=False))

    @router.websocket("/")
    async def _(request: web.Request, ws: web.WebSocket):
        auth_cookie = (await request.get_cookies()).get("auth") or None
        auth = dashboard.token_isvaild(auth_cookie.value if auth_cookie else None)
        if not auth:
            await ws.send(dashboard.to_bytes("auth", None).io.getbuffer())
        else:
            await ws.send(dashboard.to_bytes("auth", DASHBOARD_USERNAME).io.getbuffer())
        async for raw_data in ws:
            if isinstance(raw_data, str):
                return
            if isinstance(raw_data, io.BytesIO):
                raw_data = raw_data.getvalue()
            input = utils.DataInputStream(raw_data)
            type = input.readString()
            data = dashboard.deserialize(input)
            await ws.send(
                dashboard.to_bytes(
                    type, await dashboard.process(type, data)
                ).io.getbuffer()
            )

    @router.get("/auth")
    async def _(request: web.Request):
        auth = (await request.get_headers("Authorization")).split(" ", 1)[1]
        try:
            info = json.loads(base64.b64decode(auth))
        except:
            return web.Response(status_code=401)
        if (
            info["username"] != DASHBOARD_USERNAME
            or info["password"] != DASHBOARD_PASSWORD
        ):
            return web.Response(status_code=401)
        token = dashboard.generate_token(request)
        return web.Response(
            DASHBOARD_USERNAME,
            cookies=[web.Cookie("auth", token.value, expires=int(time.time() + 86400))],
        )

    @router.get("/measure")
    async def _(
        request: web.Request, config: web.ResponseConfiguration, size: int = 32
    ):
        auth_cookie = (await request.get_cookies()).get("auth") or None
        auth = dashboard.token_isvaild(auth_cookie.value if auth_cookie else None)
        if not auth:
            yield b""
            return
        config.length = size * 1024 * 1024
        for _ in range(min(1024, max(0, size))):
            yield b"\x00" * 1024 * 1024

    @router.post("/measure")
    async def _(
        request: web.Request, config: web.ResponseConfiguration, size: int = 32
    ):
        auth_cookie = (await request.get_cookies()).get("auth") or None
        auth = dashboard.token_isvaild(auth_cookie.value if auth_cookie else None)
        if not auth:
            return web.Response(status_code=401)
        if auth:
            print(await request.get_headers("Content-Length"))
            await request.skip()

    @router.post("/api/{name}")
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

    app.mount(router)
    app.redirect("/bmcl", "/bmcl/")


async def close():
    global cluster
    for plugin in plugins.get_enable_plugins():
        await plugin.disable()
    if cluster:
        await cluster.disable()
