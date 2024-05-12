import asyncio
from asyncio import exceptions
import base64
from collections import defaultdict
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
import aiohttp.client_exceptions
import socketio
from tqdm import tqdm
from core import system
from core.config import Config
from core import certificate, dashboard, unit
from core import scheduler
import pyzstd as zstd
import core.utils as utils
import core.stats as stats
import core.web as web
from core.logger import logger
import plugins
from core.i18n import locale
import aiowebdav.client as webdav3_client
import aiowebdav.exceptions as webdav3_exceptions
from core.exceptions import ClusterIdNotSet, ClusterSecretNotSet

from core.const import *

from core.api import (
    BMCLAPIFile,
    File,
    FileCheckType,
    FileContentType,
    OpenbmclapiAgentConfiguration,
    ResponseRedirects,
    Storage,
    get_hash,
)


class TokenManager:
    def __init__(self) -> None:
        self.token = None
        self.token_expires: float = 0

    async def fetchToken(self):
        async with aiohttp.ClientSession(
            headers={"User-Agent": USER_AGENT}, base_url=BASE_URL
        ) as session:
            logger.tinfo("cluster.info.token.fetching")
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
                    scheduler.delay(
                        self.fetchToken, delay=float(content["ttl"]) / 1000.0 - 600
                    )
                    self.token_expires = content["ttl"] / 1000.0 - 600 + time.time()
                    tll = utils.format_stime(content["ttl"] / 1000.0)
                    logger.tsuccess("cluster.success.token.fetched", tll=tll)

            except aiohttp.ClientError as e:
                logger.terror("cluster.error.token.failed", delay=RECONNECT_DELAY, e=e)
                try:
                    await asyncio.sleep(RECONNECT_DELAY)
                    return await self.fetchToken()
                except asyncio.CancelledError:
                    logger.error(traceback.format_exc())
                    await session.close()
                    return None

    async def getToken(self) -> str:
        if not self.token or self.token_expires <= time.time():
            await self.fetchToken()
        return self.token or ""


class ParseFileList:
    async def __call__(self, data) -> list[BMCLAPIFile]:
        self.data = io.BytesIO(data)
        self.files = [
            BMCLAPIFile(
                self.read_string(),
                self.read_string(),
                self.read_long(),
                self.read_long(),
            )
            for _ in range(self.read_long())
        ]
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
        self.last_modified: int = 0

    async def get_files(self) -> list[BMCLAPIFile]:
        async with aiohttp.ClientSession(
            base_url=BASE_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {await token.getToken()}",
            },
        ) as session:
            logger.tdebug("cluster.debug.get_files.created_session")
            async with session.get(
                "/openbmclapi/files", params={
                    "lastModified": self.last_modified
                }
            ) as req:
                logger.tdebug(
                    "cluster.debug.get_files.response_status", status=req.status
                )
                if req.status == 204:
                    return []
                if req.status != 200:
                    try:
                        req.raise_for_status()
                    except:
                        logger.error(traceback.format_exc())
                    return []
                logger.tinfo("cluster.success.get_files.requested_filelist")
                files = await ParseFileList()(zstd.decompress(await req.read()))
                self.last_modified = max(
                    (self.last_modified, *(file.mtime for file in files))
                )
                modified = utils.parse_time_to_gmt(self.last_modified / 1000)
                logger.tinfo(
                    "cluster.info.get_files.info",
                    time=modified,
                    count=unit.format_number(len(files)),
                )
                return files

    async def _download_temporarily_file(self, hash: str):
        async with aiohttp.ClientSession(
            base_url=BASE_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {await token.getToken()}",
            },
        ) as session:
            logger.tdebug("cluster.debug.download_temp.downloading", hash=hash)
            content: io.BytesIO = io.BytesIO()
            async with session.get(
                f"/openbmclapi/download/{hash}",
            ) as resp:
                while data := await resp.content.read(IO_BUFFER):
                    if not data:
                        break
                    content.write(data)
            length = len(content.getbuffer())
            h = get_hash(hash)
            h.update(content.getbuffer())
            if hash != h.hexdigest():
                logger.tdebug("cluster.debug.download_temp.failed_download", hash=hash)
                logger.error(content.getvalue().decode("utf-8"))
                return
            logger.tdebug("cluster.debug.download_temp.downloaded", hash=hash)
            await self._mount_file(
                BMCLAPIFile(
                    path=f"/download/{hash}",
                    hash=hash,
                    size=length,
                    mtime=int(time.time() * 1000),
                ),
                content,
            )
            return content

    async def _download(self, pbar: tqdm, lock: asyncio.Semaphore):
        async def put(size, file: BMCLAPIFile):
            await self.queues.put(file)
            pbar.update(-size)
        async def error(*responses: aiohttp.ClientResponse):
            msg = []
            history = list((ResponseRedirects(resp.status, str(resp.real_url)) for resp in responses))
            source = "主控" if len(history) == 1 else "节点"
            for history in history:
                msg.append(f"> {history.status} | {history.url}")
            history = '\n'.join(msg)
            logger.terror("cluster.error.download.failed", hash=file.hash, size=unit.format_bytes(file.size), 
                          source=source, host=responses[-1].host, status=responses[-1].status, history=history)
        while not self.queues.empty() and storages.available:
            async with aiohttp.ClientSession(
                BASE_URL,
                headers={
                    "User-Agent": USER_AGENT,
                    "Authorization": f"Bearer {await token.getToken()}",
                },
            ) as session:
                file = await self.queues.get()
                hash = get_hash(file.hash)
                size = 0
                content: io.BytesIO = io.BytesIO()
                resp = None
                try:
                    async with lock:
                        resp = await session.get(file.path)
                    while data := await resp.content.read(IO_BUFFER):
                        if not data:
                            break
                        byte = len(data)
                        size += byte
                        pbar.update(byte)
                        content.write(data)
                        hash.update(data)
                    resp.close()
                except asyncio.CancelledError:
                    return
                except aiohttp.client_exceptions.ClientConnectionError:
                    if resp is not None:
                        await error(*resp.history, resp)
                    await put(size, file)
                    continue
                except:
                    logger.error(traceback.format_exc())
                    if resp is not None:
                        await error(*resp.history, resp)
                    await put(size, file)
                    continue
                if file.hash != hash.hexdigest():
                    await error(*resp.history, resp)
                    await put(size, file)
                    await asyncio.sleep(5)
                    continue
                r = await self._mount_file(file, content)
                if r[0] == -1:
                    logger.terror("cluster.error.download.failed_to_upload")
                    await put(size, file)
                    continue

    async def _mount_file(
        self, file: BMCLAPIFile, buf: io.BytesIO
    ) -> tuple[int, io.BytesIO]:
        result = None
        for storage in storages.get_storages():
            r = -1
            try:
                r = await storage.write(file.hash, buf)
            except asyncio.CancelledError:
                return buf, -1
            except:
                logger.error(traceback.format_exc())
            if r != file.size:
                hash = file.hash
                file_size = unit.format_bytes(file.size)
                target_size = unit.format_bytes(r)
                logger.terror(
                    "cluster.error.mount_files.failed_to_copy",
                    hash=hash,
                    file=file_size,
                    target=target_size,
                )
                result = -1
            result = result or r
        return buf, result or -1

    async def download(self, miss: list[BMCLAPIFile], configuration: OpenbmclapiAgentConfiguration):
        if not storages.available:
            logger.terror("cluster.erorr.cluster.storage.available")
            return
        with tqdm(
            desc=locale.t("cluster.tqdm.desc.download"),
            unit="b",
            unit_divisor=1024,
            total=sum((file.size for file in miss)),
            unit_scale=True,
        ) as pbar:
            await dashboard.set_status_by_tqdm("files.downloading", pbar)
            for file in miss:
                await self.queues.put(file)
            lock = asyncio.Semaphore(configuration.concurrency)
            try:
                await asyncio.gather(*[self._download(pbar, lock) for _ in range(MAX_DOWNLOAD)])
            except asyncio.CancelledError:
                raise asyncio.CancelledError
        logger.tsuccess("cluster.info.download.finished")


class FileCheck:
    def __init__(self, downloader: FileDownloader) -> None:
        self.checked = False
        self.downloader = downloader
        self.check_type = FileCheckType.EXISTS
        if FILECHECK == "size":
            self.check_type = FileCheckType.SIZE
        elif FILECHECK == "hash":
            self.check_type = FileCheckType.HASH
        self.files = []
        self.pbar: Optional[tqdm] = None
        self.check_files_timer: Optional[int] = None
        logger.tinfo("cluster.info.check_files.check_type", type=self.check_type.name)
        self.configurations: dict[str, OpenbmclapiAgentConfiguration] = {}

    def start_task(self):
        if self.check_files_timer:
            scheduler.cancel(self.check_files_timer)
        self.check_files_timer = scheduler.delay(self.__call__, delay=1800)

    async def get_configuration(self) -> tuple[str, OpenbmclapiAgentConfiguration]:
        async with aiohttp.ClientSession(
            base_url=BASE_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {await token.getToken()}"
            }
        ) as session:
            async with session.get("/openbmclapi/configuration") as resp:
                self.configuration = {
                    key: OpenbmclapiAgentConfiguration(**value) for key, value in (await resp.json()).items()
                }
        return sorted(self.configuration.items(), key=lambda x: x[1].concurrency)[0]
    
    async def get_content_data(self, file: File) -> io.BytesIO:
        if file.is_path():
            async with aiofiles.open(file.get_data(), "rb") as r:
                return io.BytesIO(await r.read())
        elif file.is_url():
            async with aiohttp.ClientSession() as session:
                async with session.get(file.get_data()) as resp:
                    return io.BytesIO(await resp.read())
        else:
            return file.get_data()
                

    async def __call__(
        self,
    ) -> Any:
        if not self.checked:
            await dashboard.set_status("files.fetching")
        scheduler.cancel(self.check_files_timer)
        self.check_files_timer = scheduler.delay(self.__call__, delay=1800)
        files = await self.downloader.get_files()
        sorted(files, key=lambda x: x.hash)
        if not self.checked:
            await dashboard.set_status("files.checking")
        if not files:
            logger.twarn("cluster.warn.check_files.skipped")
            self.start_task()
            return
        with tqdm(
            total=len(files) * len(storages.get_storages()),
            unit=locale.t("cluster.tqdm.unit.file"),
            unit_scale=True,
        ) as pbar:
            self.pbar = pbar
            self.files = files
            await dashboard.set_status_by_tqdm("files.checking", pbar)
            pbar.set_description(locale.t("cluster.tqdm.desc.check_files"))
            try:
                miss_storage: list[list[BMCLAPIFile]] = await asyncio.gather(
                    *[
                        self.check_missing_files(storage)
                        for storage in storages.get_storages()
                    ]
                )
            except asyncio.CancelledError:
                del pbar
                raise asyncio.CancelledError

            self.pbar = None
        missing_files_by_storage: defaultdict[
                Storage, set[tuple[BMCLAPIFile, int]]
            ] = defaultdict(set)
        miss_all_files: set[BMCLAPIFile] = set()
        g_storage = storages.get_storages()
        total_missing_bytes = 0
        for storage, missing_files in zip(g_storage, miss_storage):
            for file in missing_files:
                for index_storage, other_storage in enumerate(g_storage):
                    miss_all_files.add(file)
                    if other_storage == storage:
                        continue
                    if (
                        await other_storage.exists(file.hash)
                        and await other_storage.get_size(file.hash) == file.size
                    ):
                        missing_files_by_storage[storage].add((file, index_storage))
                        total_missing_bytes += file.size
        if total_missing_bytes != 0 and len(g_storage) >= 2 and COPY_FROM_OTHER_STORAGE:
            with tqdm(
                total=total_missing_bytes,
                desc=locale.t(
                    "cluster.tqdm.desc.copying_files_from_other_storages"
                ),
                unit="B",
                unit_divisor=1024,
                unit_scale=True,
            ) as pbar:
                await dashboard.set_status_by_tqdm("files.copying", pbar)
                removes: defaultdict[Storage, set[tuple[BMCLAPIFile, int]]] = (
                    defaultdict(set)
                )
                for storage, filelist in missing_files_by_storage.items():
                    for raw_file in filelist:
                        other_storage = g_storage[raw_file[1]]
                        file = raw_file[0]
                        data = await other_storage.get(file.hash)
                        if data is None:
                            continue
                        size = await storage.write(
                            file.hash,
                            await self.get_content_data(data),
                        )
                        if size == -1:
                            hash = file.hash
                            file_size = unit.format_bytes(file.size)
                            target_size = unit.format_bytes(size)
                            logger.twarn(
                                "cluster.error.check_files.failed_to_copy",
                                hash=hash,
                                file=file_size,
                                target=target_size,
                            )
                        else:
                            removes[storage].add(raw_file)
                            pbar.update(size)
                for storage, filelist in removes.items():
                    for file in filelist:
                        if file[0] in miss_all_files:
                            miss_all_files.remove(file[0])
                        missing_files_by_storage[storage].remove(file)
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
                    desc=locale.t("cluster.tqdm.desc.delete_old_files"),
                    unit=locale.t("cluster.tqdm.unit.file"),
                    unit_scale=True,
                ) as pbar:
                    await dashboard.set_status_by_tqdm("files.delete_old", pbar)
                    for storage, filelist in more_files.items():
                        removed = await storage.removes(filelist)
                        if removed != (total := len(filelist)):
                            logger.twarn(
                                "cluster.warn.check_files.failed",
                                cur=removed,
                                total=total,
                            )
                        pbar.update(total)
        if not miss_all_files:
            file_count = len(files) * len(storages.get_storages())
            file_size = unit.format_bytes(
                sum(file.size for file in files) * len(storages.get_storages())
            )
            logger.tsuccess(
                "cluster.success.check_files.finished", count=file_count, size=file_size
            )
        else:
            logger.tinfo(
                "cluster.info.check_files.missing",
                count=unit.format_number(len(miss_all_files)),
            )
            configuration = await self.get_configuration()
            logger.tinfo("cluster.info.download.configuration", type=configuration[0], source=configuration[1].source, concurrency=configuration[1].concurrency)
            await self.downloader.download(list(miss_all_files), configuration[1])
        self.start_task()

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
            raise KeyError(f"HandlerNotFound: {self.check_type}")
        for file in self.files:
            if not await handler(file, storage):
                miss.append(file)
            self.pbar.update(1)
            await asyncio.sleep(0)
        return miss


class FileStorage(Storage):
    def __init__(self, name: str, dir: Path, width: int) -> None:
        super().__init__(name, width)
        self.dir = dir
        if self.dir.is_file():
            raise FileExistsError(f"Cannot copy file: '{self.dir}': Is a file.")
        self.dir.mkdir(exist_ok=True, parents=True)

    async def get(self, hash: str, offset: int = 0) -> File:
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
            while data := await r.read(Config.get("advanced.io_buffer")):
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


class WebDav(Storage):
    def __init__(
        self,
        name: str,
        width: int,
        username: str,
        password: str,
        hostname: str,
        endpoint: str,
    ) -> None:
        super().__init__(name, width)
        self.username = username
        self.password = password
        self.hostname = hostname
        self.endpoint = "/" + endpoint.replace("\\", "/").replace("//", "/").removesuffix("/").removeprefix('/')
        self.files: dict[str, File] = {}
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
            )
        )
        scheduler.delay(self._list_all)
        scheduler.repeat(self._keepalive, interval=60)

    async def _keepalive(self):
        try:
            hostname = self.hostname
            endpoint = self.endpoint
            await self._list_all()
            if not self.disabled:
                logger.tsuccess(
                    "cluster.success.webdav.keepalive",
                    hostname=hostname,
                    endpoint=endpoint,
                )
            else:
                storages.enable(self)
                logger.tsuccess(
                    "cluster.success.webdav.enabled",
                    hostname=hostname,
                    endpoint=endpoint,
                )
        except webdav3_exceptions.NoConnection:
            if not self.disabled:
                logger.twarn(
                    "cluster.warn.webdav.no_connection",
                    hostname=hostname,
                    endpoint=endpoint,
                )
            storages.disable(self)
            self.fetch = False
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
            storages.disable(self)
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
            raise asyncio.CancelledError
        try:
            await self._mkdir(self._download_endpoint())
            r = await self._execute(self.session.list(self._download_endpoint()))
            if r is asyncio.CancelledError:
                self.lock.acquire()
                self.fetch = False
                raise asyncio.CancelledError
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

    async def get(self, hash: str, offset: int = 0) -> File:
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
            storages.disable(self)
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


class TypeStorage(Enum):
    FILE = "file"
    WEBDAV = "webdav"


class StorageManager:
    def __init__(self) -> None:
        self._storages: list[Storage] = []
        self._interface_storage: dict[TypeStorage, Type[Storage]] = {}
        self._storage_stats: dict[Storage, stats.StorageStats] = {}
        self.available_width = False
        self.available = False
        self.storage_widths: dict[Storage, int] = {}
        self.storage_cur: int = 0

    def enable(self, storage: Storage):
        storage.disabled = False
        if not self.available and not cluster.enabled:
            self.available = True
            scheduler.delay(cluster.start)

    def disable(self, storage: Storage):
        storage.disabled = True
        if self.available and not self.get_storages():
            self.available = False
            scheduler.delay(cluster.retry)

    def add_storage(self, storage):
        self._storages.append(storage)
        type = "Unknown"
        if isinstance(storage, FileStorage):
            type = "File"
        elif isinstance(storage, WebDav):
            type = "Webdav"
        self._storage_stats[storage] = stats.get_storage(f"{type}_{storage.get_name()}")
        self.available = True
        if storage.width != -1:
            self.available_width = True
            self.storage_widths[storage] = 0

    def remove_storage(self, storage):
        self._storages.remove(storage)

    def add_interface(self, type: TypeStorage, storage: Type[Storage]):
        self._interface_storage[type] = storage

    def create_storage(self, type: TypeStorage, *args, **kwargs):
        self.add_storage(self._interface_storage[type](*args, **kwargs))

    def get_all_storages(self):
        return [storage for storage in self._storages if not storage.disabled]

    def get_storages(self):
        return [storage for storage in self._storages if not storage.disabled]

    def get_available_storages(self):
        return [
            storage
            for storage in self._storages
            if not storage.disabled and storage.width != -1
        ]

    def get_storage_stats(self):
        return self._storage_stats

    def get_storage_width(self):
        keys = list(self.storage_widths.keys())
        storage: Storage = keys[self.storage_cur]
        if self.storage_widths[storage] >= storage.width:
            self.storage_widths[storage] = 0
            self.storage_cur += 1
            if self.storage_cur >= len(keys):
                self.storage_cur = 0
                storage = keys[self.storage_cur]
        self.storage_widths[storage] += 1
        return storage

    async def get(
        self, hash: str, offset: int, ip: str, ua: str = ""
    ) -> Optional[File]:
        first_storage = self.get_storage_width()
        storage = first_storage
        exists: bool = await storage.exists(hash)
        if not exists:
            await cluster.downloader._download_temporarily_file(hash)
            exists = True
        while not (exists := await storage.exists(hash)):
            storage = self.get_storage_width()
            if storage == first_storage:
                break
        if not exists:
            return None
        file = await storage.get(hash, offset)
        if file is not None:
            self._storage_stats[storage].hit(file, offset, ip, ua)
        return file

    def get_storage_stat(self, storage):
        return self._storage_stats[storage]


class Cluster:
    def __init__(self) -> None:
        self.downloader = FileDownloader()
        self.file_check = FileCheck(self.downloader)
        self.sio = socketio.AsyncClient()
        self.sio.on("message", self._message)
        self.sio.on("exception", self._exception)
        self.enabled: bool = False
        self.cert_valid: float = 0
        self.cur_token_timestamp: float = 0
        self._retry: int = 0
        self.want_enable: bool = False
        self.disable_future: utils.WaitLock = utils.WaitLock()
        self.channel_lock: utils.WaitLock = utils.WaitLock()
        self.keepalive_timer: Optional[asyncio.TimerHandle] = None
        self.keepalive_timeout_timer: Optional[int] = None
        self.keepalive_failed: int = 0
        self.last_keepalive: Optional[float] = None

    async def connect(self):
        if not self.sio.connected:
            try:
                await self.sio.connect(
                    BASE_URL,
                    auth={"token": await token.getToken()},
                    transports=["websocket"],
                )
                self.cur_token_timestamp = token.token_expires
                await self.cert()
                return True
            except asyncio.CancelledError:
                await self.sio.disconnect()
                return False
            except:
                logger.twarn("cluster.warn.cluster.failed_to_connect")
                logger.debug(traceback.format_exc())
                scheduler.delay(self.init, delay=5)
                return False

    async def init(self):
        if not await self.connect():
            return
        await self.start()

    async def disable(self):
        if self.keepalive_timer is not None:
            self.keepalive_timer.cancel()
        if not self.enabled:
            return
        await self.disable_future.wait()
        self.disable_future.acquire()

        async def _(err, ack):
            self.disable_future.release()
            logger.tsuccess("cluster.success.cluster.disabled")
            scheduler.cancel(task)
            if err and ack:
                logger.tsuccess("cluster.success.cluster.force_exit")
                await self.sio.disconnect()

        task = scheduler.delay(_, args=(True, True), delay=5)

        await self.emit("disable", callback=_)
        await self.disable_future.wait()

    async def retry(self):
        if self.cur_token_timestamp != token.token_expires and self.sio.connected:
            await self.sio.disconnect()
            logger.tdebug("cluster.debug.cluster.socketio.disconnect")
            await self.connect()
        if RECONNECT_RETRY != -1 and self._retry >= RECONNECT_RETRY:
            logger.terror(
                "cluster.error.cluster.reached_maximum_retry_count",
                count=RECONNECT_RETRY,
            )
            return
        if self.enabled:
            await self.disable()
            self.enabled = False
        self._retry += 1
        logger.tinfo("cluster.info.cluster.retry", t=RECONNECT_DELAY)
        scheduler.delay(self.enable, delay=RECONNECT_DELAY)

    async def start(self):
        if not storages.available:
            await self.disable()
            logger.twarn("cluster.warn.cluster.no_storage")
            return
        start = time.time()
        if ENABLE and not SKIP_FILE_CHECK:
            try:
                await self.file_check()
            except asyncio.CancelledError:
                return
        t = "%.2f" % (time.time() - start)
        logger.tsuccess("cluster.success.cluster.finished_file_check", time=t)
        await self.enable()

    async def cert(self):
        if BYOC or self.cert_valid - 600 > time.time():
            return
        self.channel_lock.acquire()

        async def _(err, ack):
            if err:
                logger.terror("cluster.error.cert.failed", ack=ack)
                return
            self.cert_valid = utils.parse_iso_time(ack["expires"])
            logger.tsuccess(
                "cluster.success.cert.requested",
                time=utils.parse_datetime_to_gmt(self.cert_valid.timetuple()),
            )
            certificate.load_text(ack["cert"], ack["key"])
            await dashboard.set_status("cluster.got.cert")
            self.channel_lock.release()

        await self.emit("request-cert", callback=_)
        await dashboard.set_status("cluster.get.cert")

    async def enable(self):
        if (
            not ENABLE
            or (RECONNECT_RETRY != -1 and self._retry >= RECONNECT_RETRY)
            or not storages.available_width
        ):
            logger.twarn("cluster.warn.cluster.disabled")
            return
        if self.want_enable or self.enabled:
            logger.tdebug("cluster.debug.cluster.enable_again")
            return
        timeoutTimer = None

        async def _(err, ack):
            if timeoutTimer is not None:
                scheduler.cancel(timeoutTimer)
            self.want_enable = False
            if err:
                logger.terror(
                    "cluster.error.cluster.failed_to_start_service",
                    e=err["message"],
                )
                await self.retry()
                return
            self.enabled = True
            logger.tsuccess("cluster.success.cluster.connected_to_center_server")
            logger.tinfo(
                "cluster.info.cluster.hosting",
                id=CLUSTER_ID,
                port=PUBLIC_PORT or PORT,
            )
            await dashboard.set_status(
                "cluster.enabled" + (".trusted" if self.trusted else "")
            )
            await self.keepalive()

        async def _timeout():
            self.want_enable = False
            await self.retry()

        self.want_enable = True
        self.keepalive_failed = 0
        await self.channel_lock.wait()
        await dashboard.set_status("cluster.want_enable")
        self.trusted = True
        storage_str = {"file": 0, "webdav": 0}
        for storage in storages.get_available_storages():
            if isinstance(storage, FileStorage):
                storage_str["file"] += 1
            elif isinstance(storage, WebDav):
                storage_str["webdav"] += 1
        logger.tinfo(
            "cluster.info.cluster.storage_available_count",
            total=len(storages.get_available_storages()),
            local=storage_str["file"],
            webdav=storage_str["webdav"],
        )
        await self.emit(
            "enable",
            {
                "host": PUBLIC_HOST,
                "port": PUBLIC_PORT or PORT,
                "version": API_VERSION,
                "byoc": BYOC,
                "noFastEnable": False,
                "flavor": {
                    "runtime": f"python/{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} {VERSION}",
                    "storage": "+".join(
                        sorted((key for key, value in storage_str.items() if value))
                    ),
                },
            },
            callback=_,
        )
        timeoutTimer = scheduler.delay(_timeout, delay=ENABLE_TIMEOUT)

    async def keepalive(self):
        def _clear():
            if self.keepalive_timer is not None:
                self.keepalive_timer.cancel()
            if self.keepalive_timeout_timer is not None:
                scheduler.cancel(self.keepalive_timeout_timer)

        async def _failed():
            if self.keepalive_failed >= 3:
                await self.retry()
                return
            else:
                scheduler.delay(_start, delay=10)
            self.keepalive_failed += 1

        async def _(err, ack):
            if err:
                await self.retry()
                return
            if not ack:
                logger.terror(
                    "cluster.error.cluster.keepalive_failed",
                    count=self.keepalive_failed,
                )
                await _failed()
                return
            self.keepalive_failed = 0
            ping = int((time.time() - utils.parse_iso_time(ack).timestamp()) * 1000)
            storage_data = {"hits": 0, "bytes": 0}
            for storage in cur_storages:
                shits = max(0, storage.sync_hits)
                sbytes = max(0, storage.sync_bytes)
                storage.object.add_last_hits(shits)
                storage.object.add_last_bytes(sbytes)
                storage_data["hits"] += shits
                storage_data["bytes"] += sbytes
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

        async def _start():
            data = {"hits": 0, "bytes": 0}
            for storage in cur_storages:
                data["hits"] += max(0, storage.sync_hits)
                data["bytes"] += max(0, storage.sync_bytes)
            await self.emit(
                "keep-alive", {"time": int(time.time() * 1000), **data}, callback=_
            )

        _clear()
        self.keepalive_timer = asyncio.get_running_loop().call_later(
            60, lambda: asyncio.create_task(self.keepalive())
        )
        cur_storages = stats.get_offset_storages()
        self.keepalive_timeout_timer = scheduler.delay(_failed, delay=10)
        await _start()

    def _message(self, message):
        logger.tinfo("cluster.info.cluster.remote_message", message=message)
        if "信任度过低" in message:
            self.trusted = False

    def _exception(self, message):
        logger.terror("cluster.error.cluster.remote_message", message=message)
        scheduler.delay(self.retry)

    async def emit(self, channel, data=None, callback=None):
        logger.tdebug(
            "cluster.debug.cluster.emit.send",
            channel=channel,
            data=data,
        )
        await self.sio.emit(
            channel,
            data,
            callback=lambda x: scheduler.delay(self.message, (channel, x, callback)),
        )

    async def message(self, channel, data: list[Any], callback=None):
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


token = TokenManager()
cluster: Optional[Cluster] = None
last_status: str = "-"
storages = StorageManager()


async def init():
    if CLUSTER_ID == "":
        raise ClusterIdNotSet
    if CLUSTER_SECERT == "":
        raise ClusterSecretNotSet
    global cluster
    cluster = Cluster()
    for storage in STORAGES:
        if storage.type == "file":
            storages.add_storage(
                FileStorage(storage.name, Path(storage.path), storage.width)
            )
        elif storage.type == "webdav":
            storages.add_storage(
                WebDav(
                    storage.name,
                    storage.width,
                    storage.kwargs["username"],
                    storage.kwargs["password"],
                    storage.kwargs["endpoint"],
                    storage.path,
                )
            )
    storage_str = {"file": 0, "webdav": 0}
    for storage in storages.get_storages():
        if isinstance(storage, FileStorage):
            storage_str["file"] += 1
        elif isinstance(storage, WebDav):
            storage_str["webdav"] += 1
    logger.tinfo(
        "cluster.info.cluster.storage_count",
        total=len(storages.get_storages()),
        local=storage_str["file"],
        webdav=storage_str["webdav"],
    )
    scheduler.delay(cluster.init)
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
    async def _(request: web.Request, hash: str, config: web.ResponseConfiguration):
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
        if not storages.available_width:
            return web.Response(status_code=503)
        start_bytes = 0
        range_str = await request.get_headers("range", "")
        range_match = re.search(r"bytes=(\d+)-(\d+)", range_str, re.S) or re.search(
            r"bytes=(\d+)-", range_str, re.S
        )
        if range_match:
            start_bytes = int(range_match.group(1)) if range_match else 0
        name = {}
        if request.get_url_params().get("name"):
            name["Content-Disposition"] = (
                f"attachment; filename={request.get_url_params().get('name')}"
            )
        data = await storages.get(
            hash, start_bytes, request.get_ip(), request.get_user_agent()
        )
        if not data:
            return web.Response(status_code=404)
        config.access_log = DOWNLOAD_ACCESS_LOG
        if data.is_url() and isinstance(data.get_path(), str):
            return web.RedirectResponse(str(data.get_path()), response_configuration=config).set_headers(name)
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
    async def _(request: web.Request, namespace: str, key: int = 0):
        data = await dashboard.process(
            namespace, base64.b64decode(await request.read_all())
        )
        if "binary" in await request.get_headers("X-Accept-Encoding", ""):
            return web.Response(
                dashboard.to_bytes(key, namespace, data).io,
                headers={"X-Encoding": "binary"},
            )
        else:
            return web.Response({"data": data}, headers={"X-Encoding": "json"})

    @app.websocket("/pages/{name}/{sub}")
    @app.websocket("/pages/{name}")
    async def _(request: web.Request, ws: web.WebSocket):
        dashboard.websockets.append(ws)
        auth_cookie = (await request.get_cookies()).get("auth") or None
        auth = dashboard.token_isvaild(auth_cookie.value if auth_cookie else None)
        if not auth:
            await ws.send(dashboard.to_bytes(0, "auth", None).io.getbuffer())
        else:
            await ws.send(
                dashboard.to_bytes(0, "auth", DASHBOARD_USERNAME).io.getbuffer()
            )
        async for raw_data in ws:
            if isinstance(raw_data, str):
                continue
            if isinstance(raw_data, io.BytesIO):
                raw_data = raw_data.getvalue()
            input = utils.DataInputStream(raw_data)
            key = input.readVarInt()
            type = input.readString()
            data = dashboard.deserialize(input)
            await ws.send(
                dashboard.to_bytes(
                    key, type, await dashboard.process(type, data)
                ).io.getbuffer()
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


async def exit():
    global cluster
    for plugin in plugins.get_enable_plugins():
        await plugin.disable()
    if cluster:
        await cluster.disable()
