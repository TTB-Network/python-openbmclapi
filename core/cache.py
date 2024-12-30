import collections
import inspect
import time
from typing import Any, Iterator, MutableMapping, Optional, TypeVar

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.job import Job


T = TypeVar("T")
K = TypeVar("K")
EMPTY = inspect._empty

class CacheValue[T]:
    def __init__(self, value: T, expires: Optional[float] = None) -> None:
        self.value: T = value
        self.expires: Optional[float] = expires
        self.timestamp: float = time.monotonic_ns()
        self.job: Optional[Job] = None


# Time out cache    
class TimeoutCache(MutableMapping[K, T]):
    def __init__(self, default_timeout: Optional[float] = None):
        self.cache: collections.OrderedDict[K, CacheValue] = collections.OrderedDict()
        self.background = BackgroundScheduler()
        self.default_timeout = default_timeout
        self.background.start()

    def keys(self):
        return self.cache.keys()
    
    def set(self, key: K, value: T, timeout: Optional[float] = None) -> None:
        self._delete_job(key)
        self.cache[key] = CacheValue(
            value,
            timeout
        )
        timeout = timeout or self.default_timeout
        if timeout is not None:
            self.cache[key].job = self.background.add_job(self.delete, 'interval', seconds=timeout, args=[key, True])

    def _delete_job(self, key: K):
        current = self.cache.get(key, None)
        if current is None or current.job is None:
            return
        current.job.remove()
        current.job = None

    def get(self, key: K, _def: Any = EMPTY) -> Any:
        current = self.cache.get(key, None)
        if current is None:
            return _def
        if current.expires is not None and current.expires + current.timestamp < time.monotonic_ns():
            self.delete(key)
            return _def
        return current.value
    
    def delete(self, key: K, task: bool = False) -> None:
        self._delete_job(key)
        self.cache.pop(key, None)

    def __contains__(self, key: K) -> bool:
        if key in self.cache:
            current = self.cache[key]
            if current.expires is not None and current.expires + current.timestamp < time.monotonic_ns():
                self.delete(key)
        return key in self.cache
    
    def __delitem__(self, key: K) -> None:
        self.delete(key)

    def __getitem__(self, key: K) -> T:
        return self.get(key)

    def __setitem__(self, key: K, value: T) -> None:
        self.set(key, value)

    def __iter__(self) -> Iterator[K]:
        return iter(self.cache)

    def __len__(self) -> int:
        return len(self.cache)