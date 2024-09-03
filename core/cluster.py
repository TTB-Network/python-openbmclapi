"""
todo:
1. 支持 report API
2. 缺失文件时临时下载文件处理
"""

from core.config import Config
from core.logger import logger
from core.scheduler import *
from core.exceptions import ClusterIdNotSetError, ClusterSecretNotSetError
from core.storages import getStorages, LocalStorage
from core.classes import FileInfo, FileList, AgentConfiguration
from core.router import Router
from core.i18n import locale
from typing import List, Any
from aiohttp import web
from tqdm import tqdm
from pathlib import Path
import toml
import aiofiles
import socketio
import zstandard as zstd
import aiohttp
import asyncio
import hmac
import datetime
import hashlib
import ssl
import sys
import os
import humanize
import io
import time

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
        self.ttl = 0
        self.scheduler = None

        if not self.id or not self.secret:
            raise ClusterIdNotSetError if not self.id else ClusterSecretNotSetError

    async def fetchToken(self):
        logger.tinfo("token.info.fetching")
        async with aiohttp.ClientSession(
            self.base_url, headers={"User-Agent": self.user_agent}
        ) as session:
            response = await session.get(
                "/openbmclapi-agent/challenge", params={"clusterId": self.id}
            )
            response.raise_for_status()
            challenge = (await response.json())["challenge"]

            signature = hmac.new(
                self.secret.encode(), challenge.encode(), hashlib.sha256
            ).hexdigest()
            response = await session.post(
                "/openbmclapi-agent/token",
                data={
                    "clusterId": self.id,
                    "challenge": challenge,
                    "signature": signature,
                },
            )
            response.raise_for_status()
            res = await response.json()
            self.token = res["token"]
            self.ttl = res["ttl"] / 3600000
            logger.tsuccess("token.success.fetched", ttl=int(self.ttl))

            if not self.scheduler:
                self.scheduler = scheduler.add_job(
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
        self.runner = None
        self.failed_filelist = FileList(files=[])
        self.enabled = False
        self.site = None
        self.want_enable = False
        self.scheduler = None
        self.start_time = int(time.time() * 1000)

    async def fetchFileList(self) -> None:
        logger.tinfo("cluster.info.filelist.fetching")
        async with aiohttp.ClientSession(
            self.base_url,
            headers={
                "User-Agent": self.user_agent,
                "Authorization": f"Bearer {self.token.token}",
            },
        ) as session:
            response = await session.get(
                "/openbmclapi/files", params={"lastModified": self.last_modified}
            )
            response.raise_for_status()
            logger.tsuccess("cluster.success.filelist.fetched")

            decompressed_data = io.BytesIO(
                zstd.ZstdDecompressor()
                .stream_reader(io.BytesIO(await response.read()))
                .read()
            )
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
            response = await session.get("/openbmclapi/configuration")
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
            logger.tsuccess(
                "storage.success.get_missing",
                count=humanize.intcomma(len(missing_filelist.files)),
                size=humanize.naturalsize(
                    sum(file.size for file in missing_filelist.files), binary=True
                ),
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
                self.base_url, headers={"User-Agent": self.user_agent}
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
            delay, retry = Config.get("advanced.delay"), Config.get("advanced.retry")

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
            self.router = Router(self.application, self)
            self.router.init()
            logger.tsuccess("cluster.success.router.created")
        except Exception as e:
            logger.terror("cluster.error.router.exception", e=e)

    async def listen(self, https: bool, port: int) -> None:
        try:
            ssl_context = None
            if https:
                ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                ssl_context.load_cert_chain(
                    certfile=Path(Config.get("advanced.paths.cert")),
                    keyfile=Path(Config.get("advanced.paths.key")),
                )
                ssl_context.check_hostname = False

            self.runner = web.AppRunner(self.application)
            await self.runner.setup()
            self.site = web.TCPSite(
                self.runner, "0.0.0.0", port, ssl_context=ssl_context
            )
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
            await self.socket.emit(
                "enable",
                data={
                    "host": Config.get("cluster.host"),
                    "port": (
                        Config.get("cluster.public_port")
                        if Config.get("cluster.public_port") != -1
                        else Config.get("cluster.port")
                    ),
                    "version": API_VERSION,
                    "byoc": Config.get("cluster.byoc"),
                    "noFastEnable": True,
                    "flavor": {
                        "runtime": f"python/{sys.version.split()[0]} python-openbmclapi/{VERSION}",
                        "storage": "+".join(
                            [
                                "file"
                                for storage in self.storages
                                if isinstance(storage, LocalStorage)
                            ]
                        ),
                    },
                },
                callback=callback,
            )

            response = await future
            error, ack = (
                (response + [None, None])[:2]
                if isinstance(response, list)
                else (None, None)
            )

            if error and isinstance(error, dict) and "message" in error:
                logger.terror("cluster.error.enable.error", e=error["message"])

            if ack is not True:
                logger.terror("cluster.error.enable.failed")
                return

            self.enabled = True
            if not Config.get("cluster.byoc"):
                logger.tsuccess(
                    "cluster.success.enable.enabled",
                    id=self.id,
                    port=Config.get("cluster.public_port"),
                )
            else:
                logger.tsuccess(
                    "cluster.success.enable.enabled.byoc",
                    host=Config.get("cluster.host"),
                    port=Config.get("cluster.public_port"),
                )
            self.want_enable = True
        except Exception as e:
            logger.terror("cluster.error.enable.exception", e=e)

    async def keepAlive(self) -> bool:
        if not self.enabled:
            logger.terror("cluster.error.keep_alive.cluster_not_enabled")
            return False

        if not self.socket:
            logger.terror("cluster.error.keep_alive.socket_not_setup")
            return False

        future = asyncio.Future()

        async def callback(data: List[Any]):
            future.set_result(data)

        counter = self.router.counters

        try:
            await self.socket.emit(
                "keep-alive",
                data={"time": datetime.datetime.now().isoformat(), **counter},
                callback=callback,
            )

            response = await future
            error, date = (
                (response + [None, None])[:2]
                if isinstance(response, list)
                else (None, None)
            )

            if error:
                logger.terror("cluster.error.keep_alive.error", e=error)
                return False

            logger.tsuccess(
                "cluster.success.keep_alive.success",
                hits=humanize.intcomma(counter["hits"]),
                size=humanize.naturalsize(counter["bytes"], binary=True),
            )
            self.router.counters["bytes"] -= counter["bytes"]
            self.router.counters["hits"] -= counter["hits"]
            if not self.scheduler:
                self.scheduler = scheduler.add_job(
                    self.keepAlive,
                    IntervalTrigger(seconds=Config.get("advanced.keep_alive")),
                    max_instances=3,
                )
            return bool(date)

        except Exception as e:
            logger.terror("cluster.error.keep_alive.error", e=e)
            return False

    async def disable(self) -> None:
        if not self.socket or not self.enabled:
            return

        self.want_enable = False
        logger.tinfo("cluster.info.disabling")
        future = asyncio.Future()

        async def callback(data: List[Any]):
            future.set_result(data)

        try:
            await self.socket.emit("disable", callback=callback)

            response = await future
            error, ack = (
                (response + [None, None])[:2]
                if isinstance(response, list)
                else (None, None)
            )

            if error and isinstance(error, dict) and "message" in error:
                logger.terror("cluster.error.disable.error", e=error["message"])

            if ack is not True:
                logger.terror("cluster.error.disable.failed")

            logger.tsuccess("cluster.success.disable.disabled")
        except Exception as e:
            logger.terror("cluster.error.disable.exception", e=e)

    async def connect(self) -> None:
        if self.socket and self.socket.connected:
            return

        self.socket = socketio.AsyncClient(handle_sigint=False)

        @self.socket.on("connect")
        async def _() -> None:
            logger.tsuccess("client.success.connected")
            if self.want_enable:
                await self.enable()
                if self.scheduler:
                    self.scheduler.resume()

        @self.socket.on("disconnect")
        async def _() -> None:
            logger.twarning("client.warn.disconnected")
            self.enabled = False
            if self.scheduler:
                self.scheduler.pause()

        @self.socket.on("message")
        async def _(message: str) -> None:
            logger.tinfo("client.info.message", message=message)

        await self.socket.connect(
            self.base_url,
            transports=["websocket"],
            auth={"token": str(self.token.token)},
        )

    async def requestCertificate(self) -> None:
        cert_path, key_path = Config.get("advanced.paths.cert"), Config.get(
            "advanced.paths.key"
        )
        os.makedirs(os.path.dirname(cert_path), exist_ok=True)
        os.makedirs(os.path.dirname(key_path), exist_ok=True)

        future = asyncio.Future()

        async def callback(data: List[Any]):
            future.set_result(data)

        try:
            await self.socket.emit("request-cert", callback=callback)
            error, cert = await future
            if error:
                raise Exception(error)

            async with aiofiles.open(cert_path, "w") as f:
                await f.write(cert["cert"])
            async with aiofiles.open(key_path, "w") as f:
                await f.write(cert["key"])

            logger.tsuccess("client.success.request_certificate")
        except Exception as e:
            logger.terror("client.error.request_certificate", e=e)

    async def init(self) -> None:
        await asyncio.gather(*(storage.init() for storage in self.storages))

    async def checkStorages(self) -> bool:
        return all(
            await asyncio.gather(*(storage.check() for storage in self.storages))
        )

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
