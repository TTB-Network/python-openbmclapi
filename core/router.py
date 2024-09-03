from core.orm import writeAgent
from core.config import Config
from core.classes import Storage
from core.utils import checkSign
from core.api import getStatus
from typing import List, Union
from aiohttp import web
import random


class Router:
    def __init__(self, app: web.Application, storages: List[Storage]) -> None:
        self.app = app
        self.secret = Config.get("cluster.secret")
        self.storages = storages
        self.counters = {"hits": 0, "bytes": 0}
        self.route = web.RouteTableDef()
        self.connection = 0

    async def on_start(self, *args, **kwargs):
        self.connection = 0

    async def on_response_prepare(self, *args, **kwargs):
        self.connection += 1

    async def on_response_end(self, *args, **kwargs):
        self.connection -= 1

    def init(self) -> None:
        @self.route.get("/download/{hash}")
        async def _(
            request: web.Request,
        ) -> Union[web.Response, web.FileResponse, web.StreamResponse]:
            writeAgent(request.headers['User-Agent'], 1)
            file_hash = request.match_info.get("hash", "").lower()
            if not checkSign(file_hash, self.secret, request.query):
                return web.Response(text="Invalid signature.", status=403)

            response = None
            data = await random.choice(self.storages).express(
                file_hash, request, response
            )
            self.counters["bytes"] += data["bytes"]
            self.counters["hits"] += data["hits"]
            return response

        @self.route.get("/measure/{size}")
        async def _(request: web.Request) -> web.StreamResponse:
            try:
                size = int(request.match_info.get("size", "0"))

                if (
                    not checkSign(f"/measure/{size}", self.secret, request.query)
                    or size > 200
                ):
                    return web.Response(status=403 if size > 200 else 400)

                buffer = b"\x00\x66\xcc\xff" * 256 * 1024
                response = web.StreamResponse(
                    status=200,
                    reason="OK",
                    headers={
                        "Content-Length": str(size * 1024 * 1024),
                        "Content-Type": "application/octet-stream",
                    },
                )

                await response.prepare(request)
                for _ in range(size):
                    await response.write(buffer)
                await response.write_eof()
                return response

            except ValueError:
                return web.Response(status=400)

        @self.route.get("/api/status")
        async def _(request: web.Request) -> web.Response:
            return getStatus()

        self.app.add_routes(self.route)
        self.app.on_startup.append(self.on_start)
        self.app.on_response_prepare.append(self.on_response_prepare)
        self.app.on_cleanup.append(self.on_response_end)
