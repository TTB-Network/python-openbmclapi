from core.config import Config
from core.logger import logger
from core.scheduler import *
from core.exceptions import ClusterIdNotSetError, ClusterSecretNotSetError
from core.storages import getStorages, LocalStorage
from core.classes import FileInfo, FileList, AgentConfiguration
from core.router import Router
from core.client import WebSocketClient
from core.i18n import locale
from typing import List, Any
from aiohttp import web
from tqdm import tqdm
import toml
import zstandard as zstd
import aiohttp
import asyncio
import hmac
import hashlib
import ssl
import sys
import humanize
import io

API_VERSION = Config.get("advanced.api_version")
VERSION = toml.loads(open("pyproject.toml", "r").read())["tool"]["poetry"]["version"]


class Token:
    def __init__(self) -> None:
        self.user_agent = (
            f"openbmclapi-cluster/{API_VERSION} python-openbmclapi/{VERSION}"
        )
        self.base_url = Config.get("cluster.base_url")
        self.token = None
        self.id = Config.get("cluster.id")
        self.secret = Config.get("cluster.secret")
        self.ttl = 0  # hours
        self.scheduler = None
        self.application = None
        if not self.id or not self.secret:
            raise ClusterIdNotSetError if not self.id else ClusterSecretNotSetError

    async def fetchToken(self):
        logger.tinfo("token.info.fetching")
        async with aiohttp.ClientSession(
            self.base_url, headers={"User-Agent": self.user_agent}
        ) as session:
            async with session.get(
                "/openbmclapi-agent/challenge", params={"clusterId": self.id}
            ) as response:
                response.raise_for_status()
                challenge = (await response.json())["challenge"]

            signature = hmac.new(
                self.secret.encode(), challenge.encode(), hashlib.sha256
            )
            async with session.post(
                "/openbmclapi-agent/token",
                data={
                    "clusterId": self.id,
                    "challenge": challenge,
                    "signature": signature.hexdigest(),
                },
            ) as response:
                response.raise_for_status()
                res = await response.json()
                self.token = res["token"]
                self.ttl = res["ttl"] / 3600000
                logger.tsuccess("token.success.fetched", ttl=int(self.ttl))
                if not self.scheduler:
                    self.scheduler = Scheduler.add_job(
                        self.fetchToken, IntervalTrigger(hours=self.ttl)
                    )


class Cluster:
    def __init__(self) -> None:
        self.user_agent = (
            f"openbmclapi-cluster/{API_VERSION} python-openbmclapi/{VERSION}"
        )
        self.base_url = Config.get("cluster.base_url")
        self.last_modified = 1000
        self.id = Config.get("cluster.id")
        self.secret = Config.get("cluster.secret")
        self.token = Token()
        self.filelist = FileList(files=[])
        self.storages = getStorages()
        self.configuration = None
        self.semaphore = None
        self.socket = None
        self.router = None
        self.server = None
        self.failed_filelist = FileList(files=[])
        self.enabled = False
        self.site = None

    async def fetchFileList(self) -> None:
        logger.tinfo("cluster.info.filelist.fetching")
        async with aiohttp.ClientSession(
            self.base_url,
            headers={
                "User-Agent": self.user_agent,
                "Authorization": f"Bearer {self.token.token}",
            },
        ) as session:
            async with session.get(
                "/openbmclapi/files", params={"lastModified": self.last_modified}
            ) as response:
                response.raise_for_status()
                logger.tsuccess("cluster.success.filelist.fetched")
                decompressor = zstd.ZstdDecompressor().stream_reader(
                    io.BytesIO(await response.read())
                )
                decompressed_data = io.BytesIO(decompressor.read())
                self.filelist.files = [
                    FileInfo(
                        self.readString(decompressed_data),
                        self.readString(decompressed_data),
                        self.readLong(decompressed_data),
                        self.readLong(decompressed_data),
                    )
                    for _ in range(self.readLong(decompressed_data))
                ]
                size = sum(file.size for file in self.filelist.files)
                logger.tsuccess(
                    "cluster.success.filelist.parsed",
                    count=humanize.intcomma(len(self.filelist.files)),
                    size=humanize.naturalsize(size, binary=True),
                )

    async def getConfiguration(self) -> None:
        async with aiohttp.ClientSession(
            self.base_url,
            headers={
                "User-Agent": self.user_agent,
                "Authorization": f"Bearer {self.token.token}",
            },
        ) as session:
            async with session.get("/openbmclapi/configuration") as response:
                config_data = (await response.json())["sync"]
                self.configuration = AgentConfiguration(**config_data)
                self.semaphore = asyncio.Semaphore(self.configuration.concurrency)
        logger.tdebug("configuration.debug.get", sync=self.configuration)

    async def getMissingFiles(self) -> FileList:
        with tqdm(
            desc=locale.t("cluster.tqdm.desc.get_missing"),
            total=len(self.filelist.files) * len(self.storages),
            unit=locale.t("cluster.tqdm.unit.files"),
            unit_scale=True,
        ) as pbar:
            files = set()
            missing_files = [
                file
                for storage in self.storages
                for file in (await storage.getMissingFiles(self.filelist, pbar)).files
                if file.hash not in files and not files.add(file.hash)
            ]
            missing_filelist = FileList(files=missing_files)
            missing_files_count = len(missing_filelist.files)
            missing_files_size = sum(file.size for file in missing_filelist.files)
            logger.tsuccess(
                "storage.success.get_missing",
                count=humanize.intcomma(missing_files_count),
                size=humanize.naturalsize(missing_files_size, binary=True),
            )
            return missing_filelist

    async def syncFiles(
        self, missing_filelist: FileList, retry: int, delay: int
    ) -> None:
        if not missing_filelist.files:
            logger.tinfo("cluster.info.sync_files.skipped")
            return

        total_size = sum(file.size for file in missing_filelist.files)

        with tqdm(
            desc=locale.t("cluster.tqdm.desc.sync_files"),
            total=total_size,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            async with aiohttp.ClientSession(
                self.base_url,
                headers={"User-Agent": self.user_agent},
            ) as session:
                self.failed_filelist = FileList(files=[])
                tasks = [
                    asyncio.create_task(self.downloadFile(file, session, pbar))
                    for file in missing_filelist.files
                ]
                await asyncio.gather(*tasks)

            if not self.failed_filelist.files:
                logger.tsuccess("cluster.success.sync_files.downloaded")
            elif retry > 1:
                logger.terror("cluster.error.sync_files.retry", retry=delay)
                await asyncio.sleep(delay)
                await self.syncFiles(self.failed_filelist, retry - 1, delay)
            else:
                logger.terror("cluster.error.sync_files.failed")

    async def downloadFile(
        self, file: FileInfo, session: aiohttp.ClientSession, pbar: tqdm
    ) -> None:
        async with self.semaphore:
            delay = Config.get("advanced.delay")
            retry = Config.get("advanced.retry")

            for _ in range(retry):
                try:
                    async with session.get(file.path) as response:
                        content = await response.read()
                        results = await asyncio.gather(
                            *(
                                storage.writeFile(
                                    file, io.BytesIO(content), delay, retry
                                )
                                for storage in self.storages
                            )
                        )
                        if all(results):
                            pbar.update(len(content))
                            return
                except Exception as e:
                    logger.terror(
                        "cluster.error.download_file.retry",
                        file=file.hash,
                        e=e,
                        retry=delay,
                    )
                await asyncio.sleep(delay)
            logger.terror("cluster.error.download_file.failed", file=file.hash)
            self.failed_filelist.files.append(file)

    async def setupRouter(self) -> None:
        logger.tinfo("cluster.info.router.creating")
        try:
            self.application = web.Application()
            self.router = Router(self.application, self.storages)
            self.router.init()
            logger.tsuccess("cluster.success.router.created")
        except Exception as e:
            logger.terror("cluster.error.router.exception", e=e)

    async def listen(self, https: bool, port: int) -> None:
        try:
            ssl_context = None
            if https:
                ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                ssl_context.load_cert_chain(
                    certfile=Config.get("advanced.paths.cert"),
                    keyfile=Config.get("advanced.paths.key"),
                )
            self.server = web.AppRunner(self.application)
            await self.server.setup()
            self.site = web.TCPSite(self.server, "0.0.0.0", port, ssl_context=ssl_context)
            await self.site.start()
            logger.tsuccess("cluster.success.listen", port=port)
        except Exception as e:
            logger.terror("cluster.error.listen", e=e)

    async def enable(self) -> None:
        if self.enabled:
            return
        logger.tinfo("cluster.info.enabling")
        future = asyncio.Future()

        async def callback(data: List[Any]):
            future.set_result(data)

        if not self.socket:
            logger.terror("cluster.error.disconnected")
            return

        try:
            await self.socket.socket.emit(
                "enable",
                data={
                    "host": Config.get("cluster.host"),
                    "port": Config.get("cluster.public_port"),
                    "version": API_VERSION,
                    "byoc": Config.get("cluster.byoc"),
                    "noFastEnable": True,
                    "flavor": {
                        "runtime": f"python/{sys.version.split()[0]} python-openbmclapi/{VERSION}",
                        "storage": '+'.join(['file' for storage in self.storages if isinstance(storage, LocalStorage)])
                    },
                },
                callback=callback
            )

            response = await future
            error, ack = (response + [None, None])[:2] if isinstance(response, list) else (None, None)

            if error and isinstance(error, dict) and 'message' in error:
                logger.terror("cluster.error.enable.error", e=error['message'])

            if ack is not True:
                logger.terror("cluster.error.enable.failed")
                return

            self.enabled = True

        except Exception as e:
            logger.terror("cluster.error.enable.exception", e=e)

    async def disable(self) -> None:
        if not self.socket:
            return
        logger.tinfo("cluster.info.disabling")
        future = asyncio.Future()

        async def callback(data: List[Any]):
            future.set_result(data)

        try:
            await self.socket.socket.emit(
                "disable",
                callback=callback
            )

            response = await future
            error, ack = (response + [None, None])[:2] if isinstance(response, list) else (None, None)

            if error and isinstance(error, dict) and 'message' in error:
                logger.terror("cluster.error.disable.error", e=error['message'])

            if ack is not True:
                logger.terror("cluster.error.disable.failed")

        except Exception as e:
            logger.terror("cluster.error.enable.exception", e=e)    
    async def connect(self) -> None:
        self.socket = WebSocketClient(self.token.token)
        await self.socket.connect()

    async def init(self) -> None:
        await asyncio.gather(*(storage.init() for storage in self.storages))

    async def checkStorages(self) -> bool:
        results = await asyncio.gather(*(storage.check() for storage in self.storages))
        return all(results)

    def readLong(self, stream: io.BytesIO):
        result, shift = 0, 0
        while True:
            byte = ord(stream.read(1))
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
        return (result >> 1) ^ -(result & 1)

    def readString(self, stream: io.BytesIO):
        return stream.read(self.readLong(stream)).decode()
