import abc
import asyncio
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
from typing import Optional
import zlib

import aiofiles
from tqdm import tqdm

from core.config import Config


@dataclass
class BMCLAPIFile:
    path: str
    hash: str
    size: int

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


class Storage(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get(self, file: str) -> File:
        """
        return
            type: Path, str
            Path: Local File
            str: url
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def exists(self, hash: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_size(self, hash: str) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    async def write(self, hash: str, io: io.BytesIO) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    async def check_missing_files(
        self, pbar: tqdm, files: list[BMCLAPIFile]
    ) -> list[BMCLAPIFile]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_files(self, dir: str) -> list[str]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_files_size(self, dir: str) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    async def removes(self, hashs: list[str]) -> int:
        raise NotImplementedError


def get_hash(org):
    if len(org) == 32:
        return hashlib.md5()
    else:
        return hashlib.sha1()


async def get_file_hash(org: str, path: Path):
    hash = get_hash(org)
    async with aiofiles.open(path, "rb") as r:
        while data := await r.read(Config.get("io_buffer")):
            if not data:
                break
            hash.update(data)
            await asyncio.sleep(0.001)
    return hash.hexdigest() == org
