import abc
from dataclasses import dataclass
import inspect
import time
from typing import Any, Optional, TypeVar

from . import scheduler


T = TypeVar("T")
EMPTY = inspect._empty

@dataclass
class StorageValue:
    value: Any
    expires: Optional[float]
    timestamp: float


class Storage(metaclass=abc.ABCMeta):
    def __init__(self) -> None:
        self.cache: dict[str, StorageValue] = {}
        self._clean_task: int = -1
    @abc.abstractmethod
    def set(self, key: str, value: object, expires: Optional[float] = None) -> None:
        raise NotImplementedError
    @abc.abstractmethod
    def get(self, key: str, _def: Any = EMPTY) -> Any:
        raise NotImplementedError
    
    @abc.abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError
    
    def __setitem__(self, key: str, value: object) -> Any:
        return self.set(key, value)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key)
        if value == EMPTY:
            raise IndexError
        return value
    def exists(self, key: str) -> bool:
        obj = self.cache.get(key, None)
        return obj is not None and (obj.expires is not None and obj.expires + obj.timestamp >= time.time() or not obj.expires)
    def __contains__(self, key: str) -> bool:
        return self.exists(key)
    
    def clean(self):
        for k, v in filter(lambda x: (x[1].expires is not None and x[1].expires + x[1].timestamp >= time.time()), list(self.cache.items())):
            self.cache.pop(k)
            print(k)
        self._start_clean()


    def _start_clean(self):
        scheduler.cancel(self._clean_task)
        ready = filter(lambda x: (x.expires is not None and x.expires + x.timestamp >= time.time()), list(self.cache.values()))
        if not ready:
            return
        next_time = max(ready, key=lambda x: (x.expires + x.timestamp) - time.time()) # type: ignore
        self._clean_task = scheduler.run_later(self.clean, delay=(next_time.expires + next_time.timestamp) - time.time()) # type: ignore

    def get_keys(self) -> list[str]:
        return list(self.cache.keys())

    def get_startswith_all(self, key: str) -> dict[str, Any]:
        return {k: v for k, v in self.cache.items() if k.startswith(key)}
    
    def get_endswith_all(self, key: str) -> dict[str, Any]:
        return {k: v for k, v in self.cache.items() if k.endswith(key)}
    
    def get_contains_all(self, key: str) -> dict[str, Any]:
        return {k: v for k, v in self.cache.items() if key in k}

class MemoryStorage(Storage):
    def __init__(self) -> None:
        super().__init__()
    
    def set(self, key: str, value: object, expires: float | None = None) -> None:
        data = value
        obj = StorageValue(
            data,
            expires,
            time.time()
        )
        self.cache[key] = obj
    
    def get(self, key: str, _def: Any = EMPTY) -> Any:
        if not self.exists(key):
            return _def
        return self.cache[key].value or _def
    
    def delete(self, key: str) -> None:
        self.cache.pop(key, None)