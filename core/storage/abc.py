import abc
import tempfile

import anyio.abc

from core import utils
from core.abc import BMCLAPIFile, ResponseFile, ResponseFileNotFound, ResponseFileMemory, ResponseFileLocal, ResponseFileRemote
from ..logger import logger
from tianxiu2b2t import units
from tianxiu2b2t.anyio.concurrency import gather

MEASURE_SIZES = (10, 20, 30, 40, 50, 100, 200)

class FileInfo:
    def __init__(
        self,
        name: str,
        size: int,
        path: str
    ):
        self.name = name
        self.size = size
        self.path = CPath(path)

    def __str__(self) -> str:
        return f"{self.name} ({self.size} bytes)"
    
    def __repr__(self) -> str:
        return f"FileInfo(name={self.name}, size={self.size}, path={self.path})"
    
    def __hash__(self) -> int:
        return hash(self.name)
    
    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, FileInfo):
            return self.name == __o.name and self.size == __o.size and self.path == __o.path
        elif isinstance(__o, BMCLAPIFile):
            return self.name == __o.hash and self.size == __o.size
        return False

class Storage(metaclass=abc.ABCMeta):
    type: str = "_inerface"
    def __init__(
        self,
        name: str,
        path: str,
        weight: int,
        **kwargs
    ):
        self._name = name
        self._path = CPath(path)
        self._task_group = None
        self.readonly = False
        self.online = False
        self.weight = weight
        self.current_weight = 0
        self._kwargs = kwargs

    @property
    def cache_size(self):
        return units.parse_number_units(self._kwargs.get("cache_size", "inf"))
    
    @property
    def cache_ttl(self):
        return units.parse_time_units(self._kwargs.get("cache_ttl", "10m"))
    
    @property
    def download_dir(self):
        return bool(self._kwargs.get("add_download_dir", True))

    @abc.abstractmethod
    async def setup(
        self,
        task_group: anyio.abc.TaskGroup
    ):
        self._task_group = task_group

        task_group.start_soon(self.check_measures)


    async def check_measures(self):
        while 1:
            try:
                missings = []
                for size, res in zip(
                    MEASURE_SIZES,
                    await gather(
                        *(self._check_measure(size) for size in MEASURE_SIZES)
                    )
                ):
                    if res:
                        continue
                    missings.append(size)
                if missings:
                    logger.info(f"Storage {self.name} missing measures: {missings}")
                    await gather(
                        *(self.write_measure(size) for size in missings)
                    )
            except:
                logger.tdebug_traceback("storage.check_measures")
            
            await anyio.sleep(300)


    async def _check_measure(self, size: int) -> bool:
        try:
            return await self.check_measure(size)
        except:
            logger.ttraceback("storage.check_measure", size=size, name=self.name, type=self.type)
            return False
        

    @abc.abstractmethod
    async def check_measure(
        self,
        size: int
    ) -> bool:
        raise NotImplementedError
        

    @abc.abstractmethod
    async def list_files(
        self,
        path: str
    ) -> list[FileInfo]:
        raise NotImplementedError
    
    async def list_download_files(
        self,
        muitlpbar: utils.MultiTQDM
    ):
        res: list[FileInfo] = []
        with muitlpbar.sub(
            256,
            description=f"Listing files in {self.name}({self.type})"
        ) as pbar:
            async def works(root_ids: list[int]):
                for root_id in root_ids:
                    path = f"{root_id:02x}"
                    if self.download_dir:
                        path = f"download/{path}"
                    res.extend(await self.list_files(path))
                    pbar.update(1)
            async with anyio.create_task_group() as task_group:
                work = utils.split_workload(list(RANGE), 10)
                for w in work:
                    task_group.start_soon(works, w)
        return res

    @abc.abstractmethod
    async def upload(
        self,
        path: str,
        tmp_file: tempfile._TemporaryFileWrapper,
        size: int
    ):
        raise NotImplementedError

    async def upload_download_file(self, path: str, tmp_file: tempfile._TemporaryFileWrapper, size: int):
        if self.download_dir:
            path = f"download/{path}"
        await self.upload(f"download/{path}", tmp_file, size)

    async def get_response_file(
        self,
        hash: str
    ) -> ResponseFile:
        path = f"{hash[:2]}/{hash}"
        if self.download_dir:
            path = f"download/{path}"
        
        return await self.get_file(path)

    @abc.abstractmethod
    async def get_file(
        self,
        path: str,
    ) -> ResponseFile:
        raise NotImplementedError

    @property
    def task_group(self) -> anyio.abc.TaskGroup:
        if self._task_group is None:
            raise RuntimeError("Storage is not setup")
        return self._task_group
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def path(self) -> 'CPath':
        return self._path

    
    async def write_measure(self, size: int):
        path = f"measure/{size}"
        size = size * 1024 * 1024
        
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(b'\x00' * size)
            tmp.seek(0)
            await self.upload(
                path,
                tmp,
                size
            )
            logger.tsuccess("storage.write_measure", size=int(size / (1024 * 1024)), name=self.name, type=self.type)


    def get_py_check_path(self) -> 'CPath':
        return self.path / ".py_check"

    def emit_status(self):
        logger.debug(f"Storage {self.name} online status: {self.online}")
        utils.event.emit("storage.status", (self, self.online))

class CPath:
    def __init__(
        self,
        path: str
    ) -> None:
        self._path = CPath.convert_path(path).rstrip("/")

    # convert '\\' to '/'
    @staticmethod
    def convert_path(path: str) -> str:
        return path.replace("\\", "/")

    def __str__(self) -> str:
        return self._path
    
    def __repr__(self) -> str:
        return self._path
    
    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, CPath):
            return False
        return self._path == __o._path
    
    def __hash__(self) -> int:
        return hash(self._path)
    
    def __truediv__(self, __o: object) -> "CPath":
        if isinstance(__o, (int, float)):
            __o = str(__o)
        if not isinstance(__o, str):
            raise TypeError("unsupported operand type(s) for /: 'CPath' and '{}'".format(type(__o).__name__))
        return CPath(self._path + "/" + __o)
    
    def __rtruediv__(self, __o: object) -> "CPath":
        if isinstance(__o, (int, float)):
            __o = str(__o)
        if not isinstance(__o, str):
            raise TypeError("unsupported operand type(s) for /: '{}' and 'CPath'".format(type(__o).__name__))
        return CPath(__o + self._path)
        
    
    def __len__(self) -> int:
        return len(self._path)
    
    @property
    def parents(self) -> list['CPath']:
        paths = self._path.split("/")
        res = []
        d = ""
        for p in paths:
            if p == "":
                continue
            d += "/" + p
            res.append(CPath(d))
        res.pop()
        if not res:
            res.append(CPath("/"))
        return res
    
    @property
    def parent(self) -> 'CPath':
        return self.parents[-1]
    
    @property
    def name(self) -> str:
        if "/" in self._path:
            return self._path.split("/")[-1]
        return self._path
    

RANGE = range(0x00, 0xFF + 1)