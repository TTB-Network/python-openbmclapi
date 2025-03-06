import io
from tempfile import _TemporaryFileWrapper
import time
import aiohttp
import aiowebdav.client
import anyio
from anyio.abc._tasks import TaskGroup as TaskGroup
import cachetools

from core import logger, utils
from core.config import USER_AGENT
from . import abc
import aiowebdav

class WebDavStorage(abc.Storage):
    type = "webdav"
    def __init__(
        self,
        name: str,
        path: str,
        weight: int,
        endpoint: str,
        username: str,
        password: str,
    ):
        super().__init__(name, path, weight)
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self._cache_files: cachetools.TTLCache[str, abc.FileInfo] = cachetools.TTLCache(maxsize=1000, ttl=60)
        self._cache_redirects: cachetools.TTLCache[str, abc.ResponseFile] = cachetools.TTLCache(maxsize=1000, ttl=60)
        self._mkdir_lock = utils.Lock()

        self.client = aiowebdav.client.Client({
            "webdav_hostname": self.endpoint,
            "webdav_login": self.username,
            "webdav_password": self.password,
        })

    async def setup(self, task_group: TaskGroup):
        await super().setup(task_group)
        task_group.start_soon(self._check)
    
    async def _check(self):
        while 1:
            try:
                await self.client.upload_to(io.BytesIO(str(time.perf_counter_ns()).encode()), ".py_check")
                await self.client.clean(".py_check")
                self.online = True
            except:
                self.online = False
            finally:
                self.emit_status() 
                await anyio.sleep(60)



    async def list_files(self, path: str) -> list[abc.FileInfo]:
        result = []
        try:
            for res in await self.client.list(str(path) + "/", get_info=True):
                if res["isdir"]:
                    continue
                result.append(abc.FileInfo(
                    path=str(self._path / path / res['name']),
                    size=int(res['size']),
                    name=res['name'],
                ))
        except:
            ...
        return result
        

    async def get_file(self, path: str) -> abc.ResponseFile:
        path = str(self._path / path)
        info = self._cache_files.get(path)
        if info is None and await self.client.check(path):
            res = await self.client.info(path)
            info = abc.FileInfo(
                path=path,
                size=int(res['size']),
                name=res['name'],
            )
            self._cache_files[path] = info
        if info is None:
            return abc.ResponseFile(0)
        file = self._cache_redirects.get(path)
        if file is not None:
            return file
        async with aiohttp.ClientSession(
            auth=aiohttp.BasicAuth(self.username, self.password),
            headers={
                'User-Agent': USER_AGENT
            }
        ) as session:
            async with session.get(
                self.endpoint + path,
                allow_redirects=False
            ) as resp:
                if resp.status == 200:
                    file = abc.ResponseFileMemory(
                        data=await resp.read(),
                        size=info.size
                    )
                elif resp.status == 302 or resp.status == 301 or resp.status == 307:
                    file = abc.ResponseFileRemote(
                        url=resp.headers['Location'],
                        size=info.size
                    )
                else:
                    logger.error(f"WebDavStorage: Unknown status code {resp.status} for {path}")
        self._cache_redirects[path] = file or abc.ResponseFile(0)
        return self._cache_redirects[path]

    

    async def _mkdir(self, parent: abc.CPath):
        async with self._mkdir_lock:
            for parent in parent.parents:
                await self.client.mkdir(str(parent))

    async def upload(self, path: str, tmp_file: _TemporaryFileWrapper):
        # check dir
        await self._mkdir((self._path / path).parent)
        await self.client.upload_to(tmp_file.file, str(self._path / path))
        return True
    
    