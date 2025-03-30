from tempfile import _TemporaryFileWrapper
import time
from typing import Any
import urllib.parse as urlparse
import aiohttp
import anyio.abc
from tianxiu2b2t import units

from . import abc
from ..config import USER_AGENT
from .. import utils

class AlistResponse:
    def __init__(
        self,
        data: Any
    ):
        self.code = data["code"]
        self.data = data["data"]
        self.message = data["message"]

    def __repr__(self):
        return f"<AlistResponse code={self.code} data={self.data} message={self.message}>"
    
    def raise_for_status(self):
        if self.code == 200:
            return
        raise Exception(f"Status: {self.code}, message: {self.message}")
        

class AlistStorage(abc.Storage):
    type = "alist"
    def __init__(
        self,
        name: str,
        path: str,
        weight: int,
        endpoint: str,
        username: str,
        password: str,
        **kwargs
    ):
        super().__init__(name, path, weight, **kwargs)
        self._endpoint = endpoint
        self._username = username
        self._password = password
        self._redirect_urls: utils.UnboundTTLCache[str, abc.ResponseFile] = utils.UnboundTTLCache(
            maxsize=self.cache_size, 
            ttl=self.cache_ttl
        )
        self._token = None
    
    async def _get_token(self):
        if not self._token:
            await self._fetch_token()
        return self._token
    
    async def _fetch_token(self):
        async with aiohttp.ClientSession(
            base_url=self._endpoint,
            headers={
                "User-Agent": USER_AGENT
            }
        ) as session:
            async with session.post(
                "/api/auth/login",
                json={
                    "username": self._username,
                    "password": self._password
                }
            ) as resp:
                data = AlistResponse(await resp.json())
                data.raise_for_status()

                self._token = data.data["token"]

                assert self._task_group is not None
                utils.schedule_once(self._task_group, self._fetch_token, 3600) # refresh token every hour

    async def _check(self):
        while 1:
            async with aiohttp.ClientSession(
                base_url=self._endpoint,
                headers={
                    "Authorization": await self._get_token() or "",
                    "User-Agent": USER_AGENT
                }
            ) as session:
                try:
                    async with session.put(
                        "/api/fs/put",
                        headers={
                            "File-Path": str(self.get_py_check_path()),
                        },
                        data=str(time.perf_counter_ns())
                    ) as resp:
                        ...
                    async with session.post(
                        "/api/fs/remove",
                        data={
                            "dir": str(self._path),
                            "names": [
                                ".py_check"
                            ]
                        }
                    ) as resp:
                        ...
                    self.online = True
                except:
                    self.online = False
                finally:
                    self.emit_status()
                    await anyio.sleep(60)

    async def check_measure(self, size: int):
        path = str(self._path / "measure" / size)
        async with aiohttp.ClientSession(
            base_url=self._endpoint,
            headers={
                "Authorization": await self._get_token() or "",
                "User-Agent": USER_AGENT
            }
        ) as session:
            async with session.post(
                f"/api/fs/get",
                json={
                    "path": path
                }
            ) as resp:
                data = AlistResponse(await resp.json())
                if data.code == 200 and data.data["size"] == size * 1024 * 1024:
                    return True
        return False

    async def setup(
        self,
        task_group: anyio.abc.TaskGroup
    ):
        await super().setup(task_group)

        task_group.start_soon(self._check)

    async def list_files(self, path: str) -> list[abc.FileInfo]:
        root = self._path / path
        res = []
        async with aiohttp.ClientSession(
            base_url=self._endpoint,
            headers={
                "Authorization": await self._get_token() or "",
                "User-Agent": USER_AGENT
            }
        ) as session:
            async with session.post(
                f"/api/fs/list",
                json={
                    "path": str(root),
                }
            ) as resp:
                data = AlistResponse(await resp.json())
                for item in (data.data or {}).get("content", []) or []:
                    if item["is_dir"]:
                        continue
                    res.append(abc.FileInfo(
                        name=item["name"],
                        size=item["size"],
                        path=str(root / item["name"]),
                    ))
        return res
    
    async def upload(self, path: str, tmp_file: _TemporaryFileWrapper, size: int):
        async with aiohttp.ClientSession(
            base_url=self._endpoint,
            headers={
                "Authorization": await self._get_token() or "",
                "User-Agent": USER_AGENT
            }
        ) as session:
            async with session.put(
                f"/api/fs/put",
                headers={
                    "File-Path": urlparse.quote(str(self._path / path)),
                },
                data=tmp_file.file
            ) as resp:
                data = AlistResponse(await resp.json())
                data.raise_for_status()
                return True
    
    async def get_file(self, path: str) -> abc.ResponseFile:
        path = str(self._path / path)
        val = self._redirect_urls.get(path)
        if val is not None:
            return val
        async with aiohttp.ClientSession(
            base_url=self._endpoint,
            headers={
                "Authorization": await self._get_token() or "",
                "User-Agent": USER_AGENT
            }
        ) as session:
            async with session.post(
                f"/api/fs/get",
                json={
                    "path": path,
                }
            ) as resp:
                data = AlistResponse(await resp.json())
                self._redirect_urls[path] = abc.ResponseFileRemote(
                    url=data.data["raw_url"],
                    size=data.data["size"]
                )
        return self._redirect_urls[path]