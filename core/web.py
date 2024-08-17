from functools import wraps
from core.config import Config
import aiohttp
import aiohttp.web
import asyncio
import base64
import hashlib
import time

class Router:
    def __init__(self, https: bool, app: aiohttp.web.Application) -> None:
        self.https = https
        self.app = app
        self.secret = Config.get('cluster.secret')

    def route(self, path, method="GET"):
        def decorator(func):
            @wraps(func)
            async def wrapper(request):
                return await func(request)
            self.app.router.add_route(method, path, wrapper)
            return wrapper
        return decorator
    
    @route("/auth")
    async def _():
        pass

    @route("/download/{hash}")
    async def _(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        response = aiohttp.web.Response
        def check_sign(hash: str, secret: str, query: dict) -> bool:
            if not (s := query.get('s')) or not (e := query.get('e')): return False
            sign = base64.urlsafe_b64encode(hashlib.sha1(f"{secret}{hash}{e}".encode('utf-8')).digest()).decode('utf-8').rstrip('=')
            return sign == s and time.time() < int(e, 36)
        
        hash = request.match_info.get('hash').lower()
        async with aiohttp.ClientSession() as session:
            valid = check_sign(hash, self.secret, request.query)
            if not valid:
                return response(text="invalid sign", status=403)
            response.