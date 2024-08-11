from dataclasses import dataclass
from typing import List
from abc import ABC, abstractmethod
import io

@dataclass
class FileInfo:
    path: str
    hash: str
    size: float
    mtime: float

@dataclass
class FileList:
    files: List[FileInfo]

class Storage(ABC):

    @abstractmethod
    async def init(self) -> None:
        pass

    @abstractmethod
    async def check(self) -> bool:
        pass

    @abstractmethod
    async def writeFile(self, path: str, content: io.BytesIO) -> int:
        pass

    @abstractmethod
    async def getMissingFiles(files: FileList) -> FileList:
        pass