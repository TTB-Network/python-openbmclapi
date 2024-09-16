import abc
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import Optional

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
    async def list_files(self) -> list:
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

    async def list_files(self) -> list:
        files = []
        for root, dirs, filenames in os.walk(self.path):
            for filename in filenames:
                file = File(
                    name=filename,
                    size=os.path.getsize(os.path.join(root, filename)),
                    mtime=os.path.getmtime(os.path.join(root, filename)),
                    hash=filename
                )
                files.append(file)
        return files

    async def get_size(self, file_hash: str) -> int:
        return os.path.getsize(f"{self.path}/{file_hash[:2]}/{file_hash}")

    async def get_mtime(self, file_hash: str) -> float:
        return os.path.getmtime(f"{self.path}/{file_hash[:2]}/{file_hash}")
    
    def get_path(self, file_hash: str) -> str:
        return f"{self.path}/{file_hash[:2]}/{file_hash}"

    

class AlistStorage(iStorage): # TODO: 完成 alist 存储
    type: str = "alist"
    def __init__(self, path: str, width: int, url: str, username: Optional[str], password: Optional[str]) -> None:
        super().__init__(path, width)
        self.url = url
        self.username = username
        self.password = password
        self.can_write = username is not None and password is not None

    async def _get_token(self):
        async with aiohttp.ClientSession(
            self.url
        ) as session:
            async with session.post(
                f"{self.url}/api/auth/login",
                json = {
                    "username": self.username,
                    "password": self.password
                }
            ) as resp:
                return (await resp.json())["data"]["token"]

    def __str__(self) -> str:
        return f"Alist Storage: {self.path}"

    def __repr__(self) -> str:
        return f"AlistStorage({self.path})"
    
    