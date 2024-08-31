from core.logger import logger
from core.config import Config
from typing import List, Any
import socketio
import asyncio
import aiofiles
import os


class WebSocketClient:
    def __init__(self, token: str, cluster) -> None:
        self.socket = None
        self.base_url = Config.get("cluster.base_url")
        self.cert_path = Config.get("advanced.paths.cert")
        self.key_path = Config.get("advanced.paths.key")
        self.want_enable = True
        self.token = token
        self.cluster = cluster
        os.makedirs(os.path.dirname(self.cert_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.key_path), exist_ok=True)

    async def connect(self) -> None:
        if self.socket and self.socket.connected:
            return

        self.socket = socketio.AsyncClient(handle_sigint=False)

        @self.socket.on("connect")
        async def _() -> None:
            logger.tsuccess("client.success.connected")

        @self.socket.on("disconnect")
        async def _() -> None:
            logger.twarning("client.warn.disconnected")
            self.want_enable = False

        @self.socket.on("message")
        async def _(message: str) -> None:
            logger.tinfo("client.info.message", message=message)

        @self.socket.on("exception")
        async def _(error: str) -> None:
            logger.tinfo("client.error.exception", error=error)

        @self.socket.on("reconnect")
        async def _() -> None:
            if self.want_enable:
                await self.cluster.enable()

        @self.socket.on("reconnect_error")
        async def _(error: str) -> None:
            logger.terror("client.error.reconnect", e=error)

        @self.socket.on("reconnect_failed")
        async def _() -> None:
            pass

        await self.socket.connect(
            self.base_url, transports=["websocket"], auth={"token": str(self.token)}
        )

    async def requestCertificate(self) -> None:
        future = asyncio.Future()

        async def callback(data: List[Any]):
            error, cert = data
            future.set_result((error, cert))

        try:
            await self.socket.emit("request-cert", callback=callback)
            error, cert = await future
            if error:
                raise Exception(error)
            async with aiofiles.open(self.cert_path, "w") as f:
                await f.write(cert["cert"])
            async with aiofiles.open(self.key_path, "w") as f:
                await f.write(cert["key"])
            logger.tsuccess("client.success.request_certificate")
        except Exception as e:
            logger.terror("client.error.request_certificate", e=e)
