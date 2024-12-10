import abc
import collections
from dataclasses import dataclass
import inspect
import time
from typing import Any, Optional, TypeVar

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.job import Job


T = TypeVar("T")
EMPTY = inspect._empty

class CacheValue[T]:
    def __init__(self, value: T, expires: Optional[float] = None) -> None:
        self.value: T = value
        self.expires: Optional[float] = expires
        self.timestamp: float = time.monotonic_ns()
        self.job: Optional[Job] = None


# Time out cache    
class TimeoutCache[T]:
    def __init__(self):
        self.cache: collections.OrderedDict[str, CacheValue] = collections.OrderedDict()
        self.background = BackgroundScheduler()
    
    def set(self, key: str, value: T, timeout: Optional[float] = None) -> None:
        self._delete_job(key)
        self.cache[key] = CacheValue(
            value,
            timeout
        )
        if timeout is not None:
            self.cache[key].job = self.background.add_job(self.delete, 'interval', seconds=timeout, args=[key])

    def _delete_job(self, key: str):
        current = self.cache.get(key, None)
        if current is None or current.job is None:
            return
        current.job.remove()
        current.job = None

    def get(self, key: str, _def: Any = EMPTY) -> Any:
        current = self.cache.get(key, None)
        if current is None:
            return _def
        if current.expires is not None and current.expires + current.timestamp < time.monotonic_ns():
            self.delete(key)
            return _def
        return current.value
    
    def delete(self, key: str) -> None:
        self._delete_job(key)
        self.cache.pop(key, None)

    def __contains__(self, key: str) -> bool:
        if key in self.cache:
            current = self.cache[key]
            if current.expires is not None and current.expires + current.timestamp < time.monotonic_ns():
                self.delete(key)
        return key in self.cache