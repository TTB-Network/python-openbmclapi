import asyncio
from dataclasses import dataclass
import io
import time
from typing import Any, Optional
import urllib.parse as urlparse

import aiohttp

from core import cache, config
from core import utils
from core.logger import logger
from core.utils import WrapperTQDM

from .base import FileInfo, MeasureFile, iNetworkStorage, Range, DOWNLOAD_DIR, File, CollectionFile


ALIST_TOKEN_DEAULT_EXPIRY = 86400 * 2

@dataclass
class AlistResult:
    code: int
    message: str
    data: Any

@dataclass
class AlistToken:
    value: str
    expires: float

@dataclass
class AlistFileInfo:
    name: str
    size: int
    is_dir: bool
    modified: float
    created: float
    sign: str
    raw_url: str

class AlistError(Exception):
    def __init__(self, result: AlistResult):
        super().__init__(f"Status: {result.code}, Message: {result.message}")
        self.result = result

class AlistStorage(iNetworkStorage):
    type = "alist"

    def __init__(
        self, 
        path: str, 
        username: str, 
        password: str, 
        endpoint: str, 
        weight: int = 0, 
        list_concurrent: int = 32, 
        name: Optional[str] = None,
        cache_timeout: float = 60,
        retries: int = 3, 
        public_webdav_endpoint: str = "",
        s3_custom_host: str = ""
    ):
        super().__init__(path, username, password, endpoint, weight, list_concurrent, name, cache_timeout)
        self.retries = retries
        self.last_token: Optional[AlistToken] = None
        self.session = aiohttp.ClientSession(
            headers={
                "User-Agent": config.USER_AGENT
            }
        )
        self._public_webdav_endpoint = ""
        self._s3_custom_host = s3_custom_host
        if s3_custom_host:
            urlobject = urlparse.urlparse(s3_custom_host)
            self._s3_custom_host = f"{urlobject.scheme}://{urlobject.netloc}{urlobject.path}"
        if public_webdav_endpoint:
            urlobject = urlparse.urlparse(public_webdav_endpoint)
            self._public_webdav_endpoint = f"{urlobject.scheme}://{urlparse.quote(self.username)}:{urlparse.quote(self.password)}@{urlobject.netloc}{urlobject.path}"

    async def _get_token(self):
        if self.last_token is None or self.last_token.expires < time.monotonic():
            async with self.session.post(f"{self.endpoint}/api/auth/login", json={"username": self.username, "password": self.password}) as resp:
                r = AlistResult(
                    **(await resp.json())
                )
            try:
                if r.code == 200:
                    self.last_token = AlistToken(
                        value=r.data["token"],
                        expires=time.monotonic() + ALIST_TOKEN_DEAULT_EXPIRY - 3600
                    )
                else:
                    raise AlistError(r)
            except:
                logger.terror("storage.error.alist.fetch_token", status=r.code, message=r.message)
        if self.last_token is None:
            raise AlistError(AlistResult(500, "Failed to fetch token", None))
        return self.last_token.value
    
    async def __action_data(self, method: str, path: str, data: Any, headers: dict[str, Any] = {}, _authentication: bool = False, _retries: int = 0):
        key = hash((
            method,
            path,
            repr(headers),
            repr(data)
        ))
        res = self.cache.get(key)
        if res is not cache.EMPTY:
            return res
        async with self.session.request(
            method, f"{self.endpoint}{path}",
            data=data,
            headers={
                **headers,
                "Authorization": await self._get_token()
            }
        ) as resp:
            try:
                result = AlistResult(
                    **await resp.json()
                )
                if result.code == 401 and not _authentication:
                    self.last_token = None
                    return await self.__action_data(method, path, data, headers, True, _retries + 1)
                if result.code != 200:
                    if _retries < self.retries:
                        return await self.__action_data(method, path, data, headers, _authentication, _retries + 1)
                    logger.terror("storage.error.action_alist", method=method, url=resp.url, status=result.code, message=result.message)
                    logger.debug(data)
                    logger.debug(result)
                else:
                    self.cache.set(
                        key,
                        result,
                        60
                    )
                return result
            except:
                logger.terror("storage.error.alist", status=resp.status, message=await resp.text())
                raise
    
    async def list_files(self, pbar: WrapperTQDM) -> set[File]:
        @utils.retry(5, 10)
        async def get_files(root_id: int):
            root = self.path / DOWNLOAD_DIR / f"{root_id:02x}"
            try:
                async with sem:
                    async with self.session.post(
                        f"{self.endpoint}/api/fs/list",
                        headers={
                            "Authorization": await self._get_token()
                        },
                        data={
                            "path": str(root),
                        }
                    ) as resp:
                        result = AlistResult(
                            **await resp.json()
                        )
                        return ((result.data or {}).get("content", None) or [])
            except asyncio.CancelledError:
                raise
            except:
                logger.traceback()
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
            )
        )):
            for file in result:
                self.filelist[str(self.path / DOWNLOAD_DIR / f"{root_id:02x}" / file["name"])] = FileInfo(
                    file["size"],
                    utils.parse_isotime_to_timestamp(file["modified"]),
                )
                results.add(File(
                    file["name"],
                    file["size"],
                    utils.parse_isotime_to_timestamp(file["modified"]),
                    file["name"]
                ))

        return results
    
    async def __info_file(self, file: CollectionFile) -> AlistFileInfo:
        r = await self.__action_data(
            "post",
            "/api/fs/get",
            {
                "path": str(self.get_path(file)),
                "password": ""
            },
        )
        name = file.hash if isinstance(file, File) else str(file.size)
        if r.code == 500:
            return AlistFileInfo(
                name,
                -1,
                False,
                0,
                0,
                "",
                ""
            )
        return AlistFileInfo(
            r.data["name"],
            r.data["size"],
            r.data["is_dir"],
            utils.parse_isotime_to_timestamp(r.data["modified"]),
            utils.parse_isotime_to_timestamp(r.data["created"]),
            r.data["sign"],
            r.data["raw_url"]
        )

    async def read_file(self, file: File) -> io.BytesIO:
        info = await self.__info_file(file)
        if info.size == -1:
            return io.BytesIO()
        async with self.session.get(
            info.raw_url
        ) as resp:
            return io.BytesIO(await resp.read())
        
    async def get_url(self, file: CollectionFile) -> str:
        if self._s3_custom_host:
            return f"{self._s3_custom_host}{str(self.get_path(file))}"
        if self._public_webdav_endpoint:
            return f"{self._public_webdav_endpoint}{str(self.get_path(file))}"
        info = await self.__info_file(file)
        return '' if info.size == -1 else info.raw_url
    
    async def write_file(self, file: MeasureFile | File, content: io.BytesIO):
        path = str(self.get_path(file))
        result = await self.__action_data(
            "put",
            "/api/fs/put",
            content.getvalue(),
            {
                "File-Path": urlparse.quote(path),
            }
        )
        if result.code == 200:
            info = await self.__info_file(file)
            self.filelist[path] = FileInfo(
                info.size,
                info.modified
            )
        return result.code == 200
    
    async def close(self):
        await self.session.close()

    async def delete_file(self, file: MeasureFile | File):
        await self.__action_data(
            "post",
            "/api/fs/delete",
            {
                "path": str(self.get_path(file)),
                "password": ""
            }
        )

    async def exists(self, file: MeasureFile | File) -> bool:
        path = str(self.get_path(file))
        return path in self.filelist
    
    async def get_mtime(self, file: MeasureFile | File) -> float:
        path = str(self.get_path(file))
        if path in self.filelist:
            return self.filelist[path].mtime
        info = await self.__info_file(file)
        self.filelist[path] = FileInfo(
            info.size,
            info.modified
        )
        return info.modified
    
    async def get_size(self, file: MeasureFile | File) -> int:
        path = str(self.get_path(file))
        if path in self.filelist:
            return self.filelist[path].size
        info = await self.__info_file(file)
        self.filelist[path] = FileInfo(
            info.size,
            info.modified
        )
        return max(0, info.size)
 