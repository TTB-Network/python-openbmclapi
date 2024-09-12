from .web import routes as route
from aiohttp import web

@route.get('/dashboard/')
@route.get("/dashboard/{tail:.*}")
async def _(request: web.Request):
    return web.FileResponse("./assets/index.html")

@route.get('/')
async def _(request: web.Request):
    return web.HTTPFound('/dashboard/')

route.static("/assets", "./assets")


async def init():
    ...