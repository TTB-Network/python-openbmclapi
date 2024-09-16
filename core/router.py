from core.orm import writeAgent
from core.config import Config
from core.utils import checkSign
from core.api import getStatus
from typing import Union
from aiohttp import web
import aiohttp
from pathlib import Path
import random


class Router:
    def __init__(self, app: web.Application, cluster) -> None:
        self.app = app
        self.secret = Config.get("cluster.secret")
        self.storages = cluster.storages
        self.counters = {"hits": 0, "bytes": 0}
        self.route = web.RouteTableDef()
        self.cluster = cluster
        self.connection = 0

    def init(self) -> None:
        @self.route.get("/download/{hash}")
        async def _(
            request: web.Request,
        ) -> Union[web.Response, web.FileResponse, web.StreamResponse]:
            self.connection += 1
            writeAgent(request.headers["User-Agent"], 1)
            file_hash = request.match_info.get("hash", "").lower()
            if not checkSign(file_hash, self.secret, request.query):
                return web.Response(text="Invalid signature.", status=403)

            response = None
            data = await random.choice(self.storages).express(
                file_hash, request, response
            )
            self.counters["bytes"] += data["bytes"]
            self.counters["hits"] += data["hits"]
            self.connection -= 1
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
            return await getStatus(self.cluster)
        
        @self.route.get("/api/rank")
        async def _(request: web.Request) -> web.Response:
            async with aiohttp.ClientSession('https://bd.bangbang93.com') as session:
                data = await session.get('/openbmclapi/metric/rank')
                response = web.json_response(await data.json())
                return response

        @self.route.get("/")
        async def _(request: web.Request) -> web.HTTPFound:
            return web.HTTPFound("/dashboard")

        @self.route.get("/dashboard")
        @self.route.get("/dashboard/{tail:.*}")
        async def _(request: web.Request) -> web.FileResponse:
            return web.FileResponse("./assets/dashboard/index.html")
        
        self.route.static('/', './assets/dashboard')

        self.app.add_routes(self.route)