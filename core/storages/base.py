import abc
from dataclasses import dataclass
import hashlib
import io
from typing import Any, Optional

from core import cache
from core.utils import WrapperTQDM


DOWNLOAD_DIR = "download"
MEASURE_DIR = "measure"

@dataclass
class File:
    name: str
    size: int
    mtime: float
    hash: str

    def __hash__(self):
        return self.hash.__hash__()
    
@dataclass
class MeasureFile:
    size: int

    def __hash__(self) -> int:
        return hash(self.size)


class FilePath(object):
    def __init__(self, path: str) -> None:
        self._path = FilePath._fix_path(path)

    @staticmethod
    def _fix_path(path: str):
        return path.replace("\\", "/").rstrip("/")
    
    @property
    def parents(self):
        result = []
        for i in range(1, len(self._path.split("/"))):
            result.append(FilePath("/".join(self._path.split("/")[:i])))
        return result
    
    @property
    def parent(self):
        return FilePath(self._path.rsplit("/", 1)[-2])
    
    @property
    def name(self):
        return self._path.rsplit("/")[-1]
    
    @property
    def path(self):
        return self._path
    
    def __str__(self):
        return self._path
    
    def __repr__(self):
        return f"FilePath({self._path})"
    
    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, FilePath):
            return self._path == __o._path
        return False
    
    def __hash__(self):
        return self._path.__hash__()
    
    def __truediv__(self, __o: Any) -> 'FilePath':
        if isinstance(__o, str):
            return FilePath(self._path + "/" + __o)
        elif isinstance(__o, FilePath):
            return FilePath(self._path + "/" + __o._path)
        else:
            raise TypeError(f"Unsupported type {type(__o)}")
        
    def __rtruediv__(self, __o: Any) -> 'FilePath':
        if isinstance(__o, str):
            return FilePath(__o + "/" + self._path)
        elif isinstance(__o, FilePath):
            return FilePath(__o._path + "/" + self._path)
        else:
            raise TypeError(f"Unsupported type {type(__o)}")


CollectionFile = MeasureFile | File
Range = lambda: range(0, 256)


class iStorage(metaclass=abc.ABCMeta):
    type: str = "_interface"
    def __init__(
        self, 
        path: str, 
        weight: int = 0, 
        list_concurrent: int = 32, 
        name: Optional[str] = None
    ):
        self.path = FilePath(path)
        self.weight = weight
        self.list_concurrent = list_concurrent
        self.current_weight = 0
        self._name = name
    
    @property
    @abc.abstractmethod
    def unique_id(self):
        raise NotImplementedError("unique_id not implemented")

    @property
    def name(self):
        if self._name is None:
            return self.unique_id
        else:
            return self._name

    def __repr__(self):
        return f"{self.type}({self.path})"

    @abc.abstractmethod
    async def list_files(self, pbar: WrapperTQDM) -> set[File]:
        raise NotImplementedError("list_files not implemented")
    
    @abc.abstractmethod
    async def write_file(self, file: CollectionFile, content: io.BytesIO):
        raise NotImplementedError("write_file not implemented")
    
    @abc.abstractmethod
    async def read_file(self, file: File) -> io.BytesIO:
        raise NotImplementedError("read_file not implemented")
    
    @abc.abstractmethod
    async def delete_file(self, file: CollectionFile):
        raise NotImplementedError("delete_file not implemented")
    
    @abc.abstractmethod
    async def exists(self, file: CollectionFile) -> bool:
        raise NotImplementedError("exists not implemented")
    
    @abc.abstractmethod
    async def get_size(self, file: CollectionFile) -> int:
        raise NotImplementedError("get_size not implemented")
    
    @abc.abstractmethod
    async def get_mtime(self, file: CollectionFile) -> float:
        raise NotImplementedError("get_mtime not implemented")
    
    def get_path(self, file: CollectionFile):
        if isinstance(file, MeasureFile):
            return self.path / MEASURE_DIR / str(file.size)
        else:
            return self.path / DOWNLOAD_DIR / file.hash[:2] / file.hash


class iNetworkStorage(iStorage):
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
    ):
        super().__init__(path, weight, list_concurrent, name)
        self.username = username
        self.password = password
        self.endpoint = endpoint.rstrip("/")
        self.cache = cache.TimeoutCache(cache_timeout)

    @property
    def unique_id(self):
        return hashlib.md5(f"{self.type},{self.path},{self.endpoint}".encode("utf-8")).hexdigest()
    
    def __repr__(self):
        return f"{self.__class__.__name__}(path={self.path}, endpoint={self.endpoint})"
