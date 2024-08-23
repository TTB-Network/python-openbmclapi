from functools import wraps
from core.config import Config
from core.classes import Storage
from core.logger import logger
from core.utils import checkSign
from typing import List
from aiohttp import web
import random


class Router:
    def __init__(self, app: web.Application, storages: List[Storage]) -> None:
        self.app = app
        self.secret = Config.get("cluster.secret")
        self.storages = storages

    def route(self, path, method="GET"):
        def decorator(func):
            @wraps(func)
            async def wrapper(request):
                return await func(request)

            self.app.router.add_route(method, path, wrapper)
            return wrapper

        return decorator

    def init(self) -> None:
        @self.route("/download/{hash}")
        async def _(
            request: web.Request,
        ) -> web.Response | web.FileResponse | web.StreamResponse:
            hash = request.match_info.get("hash").lower()
            valid = checkSign(hash, self.secret, request.query)
            if not valid:
                return web.Response(text="Invalid signature.", status=403)
            response = None
            data = await random.choice(self.storages).express(hash, request, response)
            logger.debug(data)
            return response

        @self.route("/measure/{size}")
        async def _(request: web.Request):
            try:
                size = int(request.match_info['size'])
                if not checkSign(f"/measure/{size}", self.secret, request.query):
                    return web.Response(status=403)
                if size > 200:
                    return web.Response(status=400)

                buffer = b'\x00\x66\xcc\xff' * 256 * 1024
                response = web.StreamResponse(
                    status=200,
                    reason='OK',
                    headers={
                        'Content-Length': str(size * 1024 * 1024),
                        'Content-Type': 'application/octet-stream'
                    }
                )

                await response.prepare(request)
                for _ in range(size):
                    await response.write(buffer)
                await response.write_eof()
                return response

            except ValueError:
                return web.Response(status=400)
