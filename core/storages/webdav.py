import asyncio
from dataclasses import dataclass, field
import io
import time
from typing import Any, Optional
import urllib.parse as urlparse

import aiohttp

from core import cache, config
from core import utils
from core.logger import logger
from core.utils import WrapperTQDM

from .base import DOWNLOAD_DIR, FileInfo, MeasureFile, iNetworkStorage, File, CollectionFile, Range

import aiowebdav.client as webdav3_client
import aiowebdav.exceptions as webdav3_exceptions

@dataclass
class WebDavFileInfo:
    created: float
    modified: float
    name: str
    size: int

@dataclass
class WebDavFile:
    hash: str
    size: int
    url: str = ""
    data: io.BytesIO = field(default_factory=io.BytesIO)
    headers: dict[str, Any] = field(default_factory=dict)

    def set_expires(self, value: float):
        self._expires = value + time.monotonic()

    @property
    def expired(self) -> bool:
        if hasattr(self, "_expires"):
            return self._expires < time.monotonic()
        return True
    
    def data_size(self) -> int:
        return len(self.data.getbuffer())

class WebDavStorage(iNetworkStorage):
    type = "webdav"
    def __init__(
        self, 
        path: str, 
        username: str, 
        password: str, 
        endpoint: str, 
        weight: int = 0, 
        list_concurrent: int = 32,
        name: Optional[str] = None, 
        cache_timeout: int = 60,
        public_endpoint: str = "", 
        retries: int = 3
    ):
        super().__init__(path, username, password, endpoint, weight, list_concurrent, name, cache_timeout)
        self.client = webdav3_client.Client({
            "webdav_hostname": endpoint,
            "webdav_login": username,
            "webdav_password": password,
            "User-Agent": config.USER_AGENT
        })
        self.public_endpoint = public_endpoint
        self.client_lock = asyncio.Lock()
        self.session = aiohttp.ClientSession(
            auth=aiohttp.BasicAuth(username, password),
            headers={
                "User-Agent": config.USER_AGENT
            }
        )
        urlobject = urlparse.urlparse(f"{self.public_endpoint or self.endpoint}")
        self.base_url = f"{urlobject.scheme}://{urlparse.quote(self.username)}:{urlparse.quote(self.password)}@{urlobject.hostname}:{urlobject.port}{urlobject.path}"
        self.retries = retries

    async def list_files(self, pbar: WrapperTQDM) -> set[File]:
        @utils.retry(5, 10)
        async def get_files(root_id: int) -> list[WebDavFileInfo]:
            root = self.path / DOWNLOAD_DIR / f"{root_id:02x}"
            retries = 0
            while retries < self.retries:
                try:
                    async with sem:
                        result = await self.client.list(
                            str(root),
                            True
                        )
                    return [WebDavFileInfo(
                        created=utils.parse_isotime_to_timestamp(r["created"]),
                        modified=utils.parse_gmttime_to_timestamp(r["modified"]),
                        name=r["name"],
                        size=int(r["size"])
                    ) for r in result if not r["isdir"]]
                except webdav3_exceptions.RemoteResourceNotFound:
                    retries += 1
                    ...
                except:
                    logger.traceback()
                    retries += 1
                finally:
                    pbar.update(1)
            return []

        sem = asyncio.Semaphore(self.list_concurrent)
        results = set()
        for root_id, result in zip(
            Range(),
            await asyncio.gather(*(
                get_files(root_id)
                for root_id in Range()
            ))
        ):
            for file in result:
                self.filelist[str(self.path / DOWNLOAD_DIR / f"{root_id:02x}" / file.name)] = FileInfo(
                    size=file.size,
                    mtime=file.modified,
                )
                results.add(File(
                    name=file.name,
                    hash=file.name,
                    size=file.size,
                    mtime=file.modified,
                ))

        return results
    
    async def _info_file(self, file: CollectionFile) -> WebDavFileInfo:
        key = hash(file)
        res = self.cache.get(key)
        if res is not cache.EMPTY:
            return res
        try:
            res = await self.client.info(str(self.get_path(file)))
        except:
            return WebDavFileInfo(
                created=0,
                modified=0,
                name=file.hash if isinstance(file, File) else str(file.size),
                size=-1
            )
        result = WebDavFileInfo(
            created=utils.parse_isotime_to_timestamp(res["created"]),
            modified=utils.parse_gmttime_to_timestamp(res["modified"]),
            name=res["name"],
            size=int(res["size"])
        )
        self.cache.set(key, result, 60)
        return result

    async def get_mtime(self, file: MeasureFile | File) -> float:
        path = str(self.get_path(file))
        if path in self.filelist:
            return self.filelist[path].mtime
        info = await self._info_file(file)
        self.filelist[path] = FileInfo(
            size=info.size,
            mtime=info.modified,
        )
        return info.modified
    
    async def get_size(self, file: MeasureFile | File) -> int:
        path = str(self.get_path(file))
        if path in self.filelist:
            return self.filelist[path].size
        info = await self._info_file(file)
        self.filelist[path] = FileInfo(
            size=info.size,
            mtime=info.modified,
        )
        return max(0, info.size)
    
    async def exists(self, file: MeasureFile | File) -> bool:
        path = str(self.get_path(file))
        return path in self.filelist
    
    async def delete_file(self, file: MeasureFile | File):
        await self.client.unpublish(str(self.get_path(file)))
        return True
    
    async def read_file(self, file: File) -> io.BytesIO:
        data = io.BytesIO()
        if (await self._info_file(file)).size == -1:
            return data
        await self.client.download_from(data, str(self.get_path(file)))
        return data
    
    async def _mkdir(self, dir: str):
        async with self.client_lock:
            d = ""
            for x in dir.split("/"):
                d += x
                if d:
                    await self.client.mkdir(d)
                d += "/"
    
    async def get_file(self, file: CollectionFile) -> WebDavFile:
        # by old code
        f = WebDavFile(
            file.hash if isinstance(file, File) else str(file.size),
            0
        )

        # replace url to basic auth url

        url = f"{self.base_url}{self.get_path(file)}"
        f.url = url
        return f
    
    async def write_file(self, file: MeasureFile | File, content: io.BytesIO):
        path = self.get_path(file)
        await self._mkdir(str(path.parent))
        try:
            await self.client.upload_to(
                content,
                str(path),
            )
        except:
            logger.traceback()
            return False
        self.filelist[str(path)] = FileInfo(
            size=file.size,
            mtime=time.time(),
        )
        return True
    