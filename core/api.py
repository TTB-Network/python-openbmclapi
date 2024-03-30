import abc
import asyncio
from dataclasses import dataclass
from enum import Enum
import hashlib
import io
from pathlib import Path
from typing import Optional
import zlib

import aiofiles
from tqdm import tqdm

from core.config import Config


class FileCheckType(Enum):
    EXISTS = "exists"
    SIZE = "size"
    HASH = "hash"


@dataclass
class BMCLAPIFile:
    path: str
    hash: str
    size: int
    mtime: int = 0
    def __hash__(self):
        return int.from_bytes(bytes.fromhex(self.hash))

    def __eq__(self, other):
        if isinstance(other, BMCLAPIFile):
            return (
                self.hash == other.hash
                and self.size == other.size
                and self.path == other.path
            )
        return False


@dataclass
class File:
    path: Path | str
    hash: str
    size: int
    last_hit: float = 0
    last_access: float = 0
    data: Optional[io.BytesIO] = None
    cache: bool = False

    def is_url(self):
        if not isinstance(self.path, str):
            return False
        return self.path.startswith("http://") or self.path.startswith("https://")

    def get_path(self) -> str | Path:
        return self.path

    def get_data(self):
        if not self.data:
            return io.BytesIO()
        return io.BytesIO(zlib.decompress(self.data.getbuffer()))

    def set_data(self, data: io.BytesIO | memoryview | bytes):
        if not isinstance(data, io.BytesIO):
            data = io.BytesIO(data)
        self.data = io.BytesIO(zlib.compress(data.getbuffer()))


@dataclass
class StatsCache:
    total: int = 0
    bytes: int = 0


class Storage(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get(self, file: str) -> File:
        """
            get file metadata.
            return File
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def exists(self, hash: str) -> bool:
        """
        return file is exists
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_size(self, hash: str) -> int:
        """
        get file size
        return File size
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def copy(self, origin: Path, hash: str) -> int:
        """
        origin: src path
        hash: desc path (new path)
        return File size
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def write(self, hash: str, io: io.BytesIO) -> int:
        """
        hash: desc path (new path)
        io: file data
        return File size
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_files(self, dir: str) -> list[str]:
        """
        dir: path
        Getting files in a folder
        return list[str]
        """
        raise NotImplementedError
    
    @abc.abstractmethod
    async def get_hash(self, hash: str) -> str:
        """
        hash: file, length `hash` parametar, md5 length is 32, else sha1
        return hash file content
        """
        raise NotImplementedError


    @abc.abstractmethod
    async def get_files_size(self, dir: str) -> int:
        """
        dir: path
        Getting files size in a folder
        return files size
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def removes(self, hashs: list[str]) -> int:
        """
        dir: path
        Remove files (file: hash str)
        return success remove files
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_cache_stats(self) -> StatsCache:
        """
        dir: path
        Getting cache files
        return StatsCache
        """
        raise NotImplementedError


def get_hash(org):
    if len(org) == 32:
        return hashlib.md5()
    else:
        return hashlib.sha1()


async def get_file_hash(org: str, path: Path):
    hash = get_hash(org)
    async with aiofiles.open(path, "rb") as r:
        while data := await r.read(Config.get("advanced.io_buffer")):
            if not data:
                break
            hash.update(data)
            await asyncio.sleep(0.001)
    return hash.hexdigest() == org
