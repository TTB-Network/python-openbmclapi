import abc
import asyncio
from dataclasses import dataclass
from enum import Enum
import hashlib
import io
from pathlib import Path
import time
from typing import Optional
import pyzstd as zstd
import aiofiles

from core import logger, scheduler, unit, web
from core.config import Config
from core.const import CACHE_BUFFER_COMPRESSION_MIN_LENGTH, CACHE_TIME, CHECK_CACHE, CACHE_BUFFER


class FileCheckType(Enum):
    EXISTS = "exists"
    SIZE = "size"
    HASH = "hash"

class FileType(Enum):
    LOCAL = "File"
    WEBDAV = "Webdav"

class FileContentType(Enum):
    DATA = "data"
    URL = "url"
    PATH = "path"
    EMPTY = "empty"

@dataclass
class BMCLAPIFile:
    path: str
    hash: str
    size: int
    mtime: int = 0

    def __hash__(self):
        return int.from_bytes(bytes.fromhex(self.hash), byteorder="big")

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
    hash: str
    size: int
    type: FileContentType
    data: io.BytesIO | str | Path = None
    expiry: float = 0
    compressed: bool = False
    data_length: int = 0
    cache: bool = False
    headers: Optional["web.Header"] = None

    def set_data(self, data: io.BytesIO | str | Path):
        if isinstance(data, io.BytesIO):
            length = len(data.getbuffer())
            if CACHE_BUFFER_COMPRESSION_MIN_LENGTH <= length:
                self.data = io.BytesIO(zstd.compress(data.getbuffer()))
                self.data_length = len(self.data.getbuffer())
                self.compressed = True
            else:
                self.data = data
                self.data_length = len(data.getbuffer())
                self.compressed = False
            self.type = FileContentType.DATA
        elif isinstance(data, str):
            self.data_length = len(data)
            self.data = data
            self.type = FileContentType.URL
        elif isinstance(data, Path):
            self.data_length = len(str(data))
            self.data = data
            self.type = FileContentType.PATH

    def get_data(self):
        if self.compressed:
            return io.BytesIO(zstd.decompress(self.data.getbuffer()))
        else:
            return self.data
    def is_url(self):
        return self.type == FileContentType.URL
    def is_path(self):
        return self.type == FileContentType.PATH
    def get_path(self) -> Path:
        return self.data
@dataclass
class StatsCache:
    total: int = 0
    bytes: int = 0
    data_bytes: int = 0


class Storage(metaclass=abc.ABCMeta):
    def __init__(self, name, type: str, width: int) -> None:
        self.name = name
        self.disabled = False
        self.width = width
        self.type: str = type
        self.cache: dict[str, File] = {}
        self.cache_timer = scheduler.repeat(
            self.clear_cache, delay=CHECK_CACHE, interval=CHECK_CACHE
        )
    def get_name(self):
        return self.name
    
    def get_type(self):
        return self.type

    def get_cache(self, hash: str) -> Optional[File]:
        file = self.cache.get(hash, None)
        if file is not None:
            file.cache = True
            if not file.is_url():
                file.expiry = time.time() + CACHE_TIME
        return file
    
    def is_cache(self, hash: str) -> Optional[File]:
        return hash in self.cache

    def set_cache(self, hash: str, file: File):
        self.cache[hash] = file

    def clear_cache(self):
        hashs = set()
        data = sorted(
            self.cache.copy().items(), 
            key=lambda x: x[1].expiry, reverse=True)
        size = 0
        old_size = 0
        for hash, file in data:
            if file.type == FileContentType.EMPTY:
                continue
            size += file.data_length
            if (size <= CACHE_BUFFER and file.expiry >= time.time()):
                continue
            hashs.add(hash)
            old_size += file.data_length
        for hash in hashs:
            self.cache.pop(hash)
        logger.tinfo(
            "cluster.info.clear_cache.count",
            name=self.name,
            count=unit.format_number(len(hashs)),
            size=unit.format_bytes(old_size),
        )

    def get_cache_stats(self) -> StatsCache:
        stat = StatsCache()
        for file in self.cache.values():
            stat.total += 1
            stat.bytes += file.size
            stat.data_bytes += file.data_length
        return stat

    @abc.abstractmethod
    async def get(self, file: str, start: int = 0, end: Optional[int] = None) -> File:
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

@dataclass
class OpenbmclapiAgentConfiguration:
    source: str
    concurrency: int

@dataclass
class ResponseRedirects:
    status: int 
    url: str

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
