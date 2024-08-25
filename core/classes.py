from dataclasses import dataclass
from typing import List, Dict, Any
from abc import ABC, abstractmethod
import io
from aiohttp import web
import tqdm


@dataclass
class FileInfo:
    path: str
    hash: str
    size: int
    mtime: int


@dataclass
class FileList:
    files: List[FileInfo]


@dataclass
class AgentConfiguration:
    source: str
    concurrency: int


@dataclass
class Counters:
    hits: int
    bytes: int


class Storage(ABC):
    @abstractmethod
    async def init(self) -> None:
        pass

    @abstractmethod
    async def check(self) -> bool:
        pass

    @abstractmethod
    async def writeFile(
        self, path: str, content: io.BytesIO, delay: int, retry: int
    ) -> int:
        pass

    @abstractmethod
    async def getMissingFiles(files: FileList, pbar: tqdm) -> FileList:
        pass

    @abstractmethod
    async def express(
        hash: str, request: web.Request, response: web.StreamResponse
    ) -> Dict[str, Any]:
        pass
