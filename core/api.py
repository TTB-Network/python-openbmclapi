import abc
import asyncio
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import time
from types import TracebackType
from typing import Any, Iterable, Mapping, Optional
import zlib

import aiofiles
from tqdm import tqdm


@dataclass
class BMCLAPIFile:
    path: str
    hash: str
    size: int
    def __hash__(self):  
        return int.from_bytes(bytes.fromhex(self.hash))
  
    def __eq__(self, other):  
        if isinstance(other, BMCLAPIFile):  
            return self.hash == other.hash and self.size == other.size and self.path == other.path  
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
    async def check_missing_files(self, pbar: tqdm, files: list[BMCLAPIFile]) -> list[BMCLAPIFile]:
        raise NotImplementedError

"""class FixTQDM(org_tqdm):  
    def __init__(self, 
                 iterable: Optional[Iterable[Any]] = None, 
                 desc: str | None = None, 
                 total: float | None = None, 
                 leave: bool | None = True, 
                 file: str | None = None, 
                 ncols: int | None = None, 
                 mininterval: float = 0.1, 
                 maxinterval: float = 10, 
                 miniters: float | None = None, 
                 ascii: bool | str | None = None, 
                 unit: str = "it", 
                 unit_scale: bool | float = False, 
                 dynamic_ncols: bool = False, 
                 smoothing: float = 0.3, 
                 bar_format: str | None = None, 
                 initial: float = 0, 
                 position: int | None = None, 
                 postfix: Mapping[str, object] | str | None = None, 
                 unit_divisor: float = 1000, 
                 write_bytes: bool = False, 
                 lock_args: tuple[bool | None, float | None] | tuple[bool | None] | None = None, 
                 nrows: int | None = None, 
                 colour: str | None = None, 
                 delay: float | None = 0, 
                 gui: bool = False, 
                 refresh_rate: float = 0,
                 **kwargs: Any):
        super().__init__(
                 iterable = iterable, # type: ignore
                 desc = desc,
                 total = total,
                 leave = leave,
                 file = file, # type: ignore
                 ncols = ncols,
                 mininterval = mininterval,
                 maxinterval = maxinterval,
                 miniters = miniters,
                 ascii = ascii,
                 disable = False,
                 unit = unit,
                 unit_scale = unit_scale,
                 dynamic_ncols = dynamic_ncols,
                 smoothing = smoothing,
                 bar_format = bar_format,
                 initial = initial,
                 position = position,
                 postfix = postfix,
                 unit_divisor = unit_divisor,
                 write_bytes = write_bytes,
                 lock_args = lock_args,
                 nrows = nrows,
                 colour = colour,
                 delay = delay,
                 gui = gui,
                 **kwargs
        )
        self.value = 0
        self.last_time = 0
        self.interval = refresh_rate
    def update(self, n=1):  
        self.value += n or 0
        self._update()
    def _update(self):
        if self.interval + self.last_time >= time.time():
            return
        super().update(self.value)
        self.value = 0
        self.last_time = time.time()
    def close(self) -> None:
        self._update()
        return super().close()
    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
        self._update()
        return super().__exit__(exc_type, exc_value, traceback)
"""
    

def get_hash(org):
    if len(org) == 32:
        return hashlib.md5()
    else:
        return hashlib.sha1()


async def get_file_hash(org: str, path: Path):
    hash = get_hash(org)
    async with aiofiles.open(path, "rb") as r:
        while data := await r.read(Config.get("io_buffer")): # type: ignore
            if not data:
                break
            hash.update(data)
            await asyncio.sleep(0.001)
    return hash.hexdigest() == org