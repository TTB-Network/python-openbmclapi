import abc
import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import time
from typing import Any, Optional

from tqdm import tqdm

from core import units
from .. import scheduler, utils, cache
from ..logger import logger
import urllib.parse as urlparse

import aiofiles
import aiohttp

@dataclass
class File:
    name: str
    size: int
    mtime: float
    hash: str


class iStorage(metaclass=abc.ABCMeta):
    type: str = "_interface"
    can_write: bool = False

    def __init__(self, path: str, width: int) -> None:
        if self.type == "_interface":
            raise ValueError("Cannot instantiate interface")
        self.path = path
        self.width = width
        self.unique_id = hashlib.md5(f"{self.type},{self.path}".encode("utf-8")).hexdigest()
        self.current_width = 0
        self.cache_files = cache.MemoryStorage()

    def __repr__(self) -> str:
        return f"{self.type}({self.path})"
    
    @abc.abstractmethod
    async def write_file(self, file: File, content: bytes, mtime: Optional[float]) -> bool:
        raise NotImplementedError("Not implemented")
    @abc.abstractmethod
    async def read_file(self, file_hash: str) -> bytes:
        raise NotImplementedError("Not implemented")
    @abc.abstractmethod
    async def delete_file(self, file_hash: str) -> bool:
        raise NotImplementedError("Not implemented")
    @abc.abstractmethod
    async def list_files(self, pbar: Optional[tqdm] = None) -> defaultdict[str, deque[File]]:
        raise NotImplementedError("Not implemented")
    @abc.abstractmethod
    async def exists(self, file_hash: str) -> bool:
        raise NotImplementedError("Not implemented")
    @abc.abstractmethod
    async def get_size(self, file_hash: str) -> int:
        raise NotImplementedError("Not implemented")
    @abc.abstractmethod
    async def get_mtime(self, file_hash: str) -> float:
        raise NotImplementedError("Not implemented")
    
    def get_path(self, file_hash: str) -> str:
        return f"{self.path}/{file_hash[:2]}/{file_hash}"


class LocalStorage(iStorage):
    type: str = "local"
    can_write: bool = True
    def __init__(self, path: str, width: int) -> None:
        super().__init__(path, width)

    def __str__(self) -> str:
        return f"Local Storage: {self.path}"
    
    def __repr__(self) -> str:
        return f"LocalStorage({self.path})"
    
    async def write_file(self, file: File, content: bytes, mtime: Optional[float]) -> bool:
        Path(f"{self.path}/{file.hash[:2]}").mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(f"{self.path}/{file.hash[:2]}/{file.hash}", "wb") as f:
            await f.write(content)
        return True

    async def read_file(self, file_hash: str) -> bytes:
        if not await self.exists(file_hash):
            raise FileNotFoundError(f"File {file_hash} not found")
        async with aiofiles.open(f"{self.path}/{file_hash[:2]}/{file_hash}", "rb") as f:
            return await f.read()

    async def exists(self, file_hash: str) -> bool:
        return os.path.exists(f"{self.path}/{file_hash[:2]}/{file_hash}")

    async def delete_file(self, file_hash: str) -> bool:
        if not await self.exists(file_hash):
            return False
        os.remove(f"{self.path}/{file_hash[:2]}/{file_hash}")
        return True

    async def list_files(self, pbar: Optional[tqdm] = None) -> dict[str, deque[File]]:
        def update():
            pbar.update(1) # type: ignore
        def empty():
            ...
        update_tqdm = empty
        if pbar is not None:
            update_tqdm = update

        files: defaultdict[str, deque[File]] = defaultdict(deque)
        for root_id in range(0, 256):
            root = f"{self.path}/{root_id:02x}"
            if not os.path.exists(root):
                update_tqdm()
                continue
            for file in os.listdir(root):
                path = os.path.join(root, file)
                if not os.path.isfile(path):
                    continue
                files[root].append(File(
                    file,
                    os.path.getsize(path),
                    os.path.getmtime(path),
                    file
                ))
                await asyncio.sleep(0)
            update_tqdm()
        return files

    async def get_size(self, file_hash: str) -> int:
        return os.path.getsize(f"{self.path}/{file_hash[:2]}/{file_hash}")

    async def get_mtime(self, file_hash: str) -> float:
        return os.path.getmtime(f"{self.path}/{file_hash[:2]}/{file_hash}")


@dataclass
class AlistFileInfo:
    name: str
    size: int
    is_dir: bool
    modified: float
    created: float
    sign: str
    raw_url: str

@dataclass
class AlistResult:
    code: int
    message: str
    data: Any

class AlistPath:
    def __init__(self, path: str):
        self.path = path if path.startswith("/") else f"/{path}"
    
    @property
    def parent(self):
        if self.path == "/":
            return None
        return AlistPath("/".join(self.path.split("/")[:-1]))

    @property
    def parents(self):
        return [AlistPath("/".join(self.path.split("/")[:-i])) for i in range(1, len(self.path.split("/")))]

    @property
    def name(self):
        return self.path.split("/")[-1]

    def __div__(self, other: object):
        if isinstance(other, AlistPath):
            return AlistPath(f"{self.path}/{other.path}")
        return AlistPath(f"{self.path}{other}")
    
    def __truediv__(self, other: object):
        return self.__div__(other)
    
    def __add__(self, other: 'AlistPath'):
        return AlistPath(f"{self.path}{other.path}")
    
    def __repr__(self):
        return f"AlistPath({self.path})"
    
    def __str__(self):
        return self.path

@dataclass
class AlistLink:
    url: str = ""
    _expires: Optional[float] = None

    def set_url(self, url: str, expired: Optional[float] = None):
        self.url = url
        if expired is None:
            return
        self._expires = expired + time.monotonic()
        
    @property
    def expired(self):
        return self._expires is None or self._expires > time.monotonic()
            

    

class AlistStorage(iStorage): # TODO: 修复路径
    type: str = "alist"
    def __init__(self, path: str, width: int, url: str, username: Optional[str], password: Optional[str], link_cache_expires: Optional[str] = None) -> None:
        super().__init__(path[0:-1] if path.endswith("/") else path, width)
        self.url = url
        self.username = username
        self.password = password
        self.can_write = username is not None and password is not None
        self.fetch_token = None
        self.last_token = 0
        self.wait_token = utils.CountLock()
        self.wait_token.acquire()
        self.tcp_connector = aiohttp.TCPConnector(limit=256)
        self.download_connector = aiohttp.TCPConnector(limit=256)
        self.cache = cache.MemoryStorage()
        self.link_cache_timeout = utils.parse_time(link_cache_expires).to_seconds if link_cache_expires is not None else None
        self.link_cache: defaultdict[str, AlistLink] = defaultdict(lambda: AlistLink())
        scheduler.run_repeat_later(self._check_token, 0, 3600)
        if self.link_cache_timeout is not None:
            logger.tinfo("storage.info.alist.link_cache", raw=link_cache_expires, time=units.format_count_datetime(self.link_cache_timeout))
        else:
            logger.tinfo("storage.info.alist.link_cache", raw=link_cache_expires, time="disabled")
        self.session = aiohttp.ClientSession(
            self.url
        )

    async def _get_token(self):
        await self.wait_token.wait()
        return str(self.fetch_token)

    async def _check_token(self):
        async def _check():
            if self.fetch_token is None or self.last_token + 172000 < time.time():
                return False
            async with session.get(
                "/api/me",
                headers={
                    "Authorization": str(self.fetch_token)
                }
            ) as resp:
                return AlistResult(
                    **await resp.json()
                ).code != 200
            
        async def _fetch():
            async with session.post(
                f"/api/auth/login",
                json = {
                    "username": self.username,
                    "password": self.password
                }
            ) as resp:
                return AlistResult(
                    **await resp.json()
                )

        async with aiohttp.ClientSession(
            self.url
        ) as session:
            if not await _check(): # type: ignore
                r = await _fetch()
                if r.code == 200:
                    self.fetch_token = r.data["token"]
                    self.last_token = time.time()
                    self.wait_token.release()
                else:
                    logger.terror("storage.error.alist.fetch_token", status=r.code, message=r.message)
                
    def __str__(self) -> str:
        return f"Alist Storage: {self.path}"

    def __repr__(self) -> str:
        return f"AlistStorage({self.path})"

    async def _action_data(self, action: str, url: str, data: Any, headers: dict[str, str] = {}, session: Optional[aiohttp.ClientSession] = None) -> AlistResult:
        hash = hashlib.sha256(f"{action},{url},{data},{headers}".encode()).hexdigest()
        if hash in self.cache:
            return self.cache.get(hash)
        session = self.session
        async with session.request(
            action, url,
            data=data,
            headers={
                **headers,
                **{
                    "Authorization": await self._get_token()
                }
            }
        ) as resp:
            try:
                result = AlistResult(
                    **await resp.json()
                )
                if result.code != 200:
                    logger.terror("storage.error.action_alist", method=action, url=url, status=result.code, message=result.message)
                    logger.debug(data)
                    logger.debug(result)
                else:
                    self.cache.set(hash, result, 30)
                return result
            except:
                logger.terror("storage.error.alist", status=resp.status, message=await resp.text())
                raise

    async def __info_file(self, file_hash: str) -> AlistFileInfo:
        r = await self._action_data(
            "post",
            "/api/fs/get",
            {
                "path": self.get_path(file_hash),
                "password": ""
            }
        )
        if r.code == 500:
            return AlistFileInfo(
                file_hash,
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

    async def delete_file(self, file_hash: str) -> bool:
        result = await self._action_data(
            "post",
            "/api/fs/remove",
            {
                "names": [
                    file_hash
                ],
                "dir": f"{self.path}/{file_hash[:2]}"
            }
        )
        return result.code == 200
    
    async def exists(self, file_hash: str) -> bool:
        info = await self.__info_file(file_hash)
        return info.size != -1
    
    async def get_mtime(self, file_hash: str) -> float:
        return (await self.__info_file(file_hash)).modified
    
    async def get_size(self, file_hash: str) -> int:
        info = await self.__info_file(file_hash)
        return max(0, info.size)

    async def list_files(self, pbar: Optional[tqdm] = None) -> defaultdict[str, deque[File]]:
        def update():
            pbar.update(1) # type: ignore
        def empty():
            ...
        update_tqdm = empty
        if pbar is not None:
            update_tqdm = update
    
        files: defaultdict[str, deque[File]] = defaultdict(deque)
        async def get_files(root_id: int):
            root = f"{self.path}/{root_id:02x}"
            if f"listfile_{root}" in self.cache:
                result = self.cache.get(f"listfile_{root}")
            else:
                try:
                    async with session.post(
                        "/api/fs/list",
                        data={
                            "path": str(root)
                        },
                    ) as resp:
                        result = AlistResult(
                            **await resp.json()
                        )
                        if result.code != 200:
                            logger.tdebug("storage.debug.error_alist", status=result.code, message=result.message)
                        else:
                            self.cache.set(f"listfile_{root}", result, 60)
                except:
                    logger.traceback()
                    return []
            return ((result.data or {}).get("content", None) or [])
        async with aiohttp.ClientSession(
            self.url,
            headers={
                "Authorization": await self._get_token()
            }
        ) as session:
            results = await asyncio.gather(
                *(get_files(root_id) for root_id in range(256))
            )
            for root_id, result in zip(
                range(256), results
            ):
                for r in result:
                    file = File(
                        r["name"],
                        r["size"],
                        utils.parse_isotime_to_timestamp(r["modified"]),
                        r["name"]
                    )
                    files[f"{root_id:02x}"].append(file)
                await asyncio.sleep(0)
                update_tqdm()
            
        return files
    
    async def read_file(self, file_hash: str) -> bytes:
        info = await self.__info_file(file_hash)
        if info.size == -1:
            return b''
        async with aiohttp.ClientSession(
            connector=self.download_connector
        ) as session:
            async with session.get(
                info.raw_url
            ) as resp:
                return await resp.read()

    async def get_url(self, file_hash: str) -> str:
        cache = self.link_cache[file_hash]
        if cache.expired:
            info = await self.__info_file(file_hash)
            cache.set_url('' if info.size == -1 else info.raw_url, self.link_cache_timeout)
        return cache.url

    async def write_file(self, file: File, content: bytes, mtime: float | None) -> bool:
        result = await self._action_data(
            "put",
            "/api/fs/put",
            content,
            {
                "File-Path": urlparse.quote(self.get_path(file.hash))
            }
        )
        return result.code == 200
    
    async def close(self):
        await self.session.close()