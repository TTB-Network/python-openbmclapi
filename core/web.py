import asyncio
import time
from typing import Any, Optional
from aiohttp import web
from aiohttp.web_urldispatcher import SystemRoute

from . import units
from . import config
from .logger import logger

@web.middleware
async def middleware(request: web.Request, handler: Any) -> web.Response:
    with request.match_info.set_current_app(app):
        start = time.monotonic_ns()
        resp = None
        try:
            resp = await handler(request)
            return resp
        finally:
            status = 500
            if isinstance(request.match_info.route, SystemRoute):
                status = request.match_info.route.status
            if resp is not None:
                if isinstance(resp, web.StreamResponse):
                    status = resp.status
            end = time.monotonic_ns()
            logger.tdebug("web.debug.request_info", time=units.format_count_time(end - start, 4).rjust(16), host=request.host, address=(request.remote or "").rjust(16), user_agent=request.headers.get("User-Agent"), real_path=request.raw_path, method=request.method.ljust(9), status=status)


routes = web.RouteTableDef()

app = web.Application(
    middlewares=[
        middleware
    ]
)
runner: Optional[web.AppRunner] = None
site: Optional[web.TCPSite] = None
public_server: Optional[asyncio.Server] = None

async def get_free_port():
    async def _(_, __):
        ...
    server = await asyncio.start_server(_, port=-1)
    port = server.sockets[0].getsockname()[1]
    server.close()
    await server.wait_closed()
    return port

async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    ...

async def init():
    global runner, site, public_server, routes, app

    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()

    port = await get_free_port()

    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    logger.tdebug("web.debug.local_port", port=site._port)


    public_server = await asyncio.start_server(
        handle, port=config.const.public_port
    )
    logger.tsuccess("web.success.public_port", port=config.const.public_port)


async def unload():
    global app
    await app.cleanup()
    await app.shutdown()