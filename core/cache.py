import functools
import inspect
import time
from typing import Any, Iterator, MutableMapping, Optional, TypeVar

from core import scheduler

T = TypeVar("T")
K = TypeVar("K")
EMPTY = inspect._empty

class CacheValue[T]:
    def __init__(self, value: T, expires: Optional[float] = None) -> None:
        self.value: T = value
        self.expires: Optional[float] = expires
        self.timestamp: float = time.monotonic()

class TimeoutCache(MutableMapping[K, T]):
    def __init__(self, default_timeout: Optional[float] = None):
        self.cache: dict[K, CacheValue] = {}
        self.default_timeout = default_timeout
        if self.default_timeout is None:
            return
        self.scheduler = scheduler.run_repeat_later(self._prune, self.default_timeout, self.default_timeout)

    def _prune(self):
        current_time = time.monotonic()
        keys_to_delete = [key for key, cache_value in self.cache.items() if cache_value.expires is not None and cache_value.expires < current_time]
        for key in keys_to_delete:
            del self.cache[key]

    def keys(self):
        self._prune()
        return self.cache.keys()

    def set(self, key: K, value: T, timeout: Optional[float] = None) -> None:
        self.cache[key] = CacheValue(value, timeout or self.default_timeout)

    def get(self, key: K, _def: Any = EMPTY) -> Any:
        self._prune()
        if key not in self.cache:
            return _def
        cache_value = self.cache[key]
        if cache_value.expires is not None and cache_value.expires < time.monotonic():
            return _def
        return cache_value.value

    def delete(self, key: K) -> None:
        if key in self.cache:
            del self.cache[key]

    def __contains__(self, key: K) -> bool:
        self._prune()
        return key in self.cache

    def __delitem__(self, key: K) -> None:
        self.delete(key)

    def __getitem__(self, key: K) -> T:
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: K, value: T) -> None:
        self.set(key, value)

    def __iter__(self) -> Iterator[K]:
        self._prune()
        return iter(self.cache)

    def __len__(self) -> int:
        self._prune()
        return len(self.cache)
    
    def __del__(self):
        if hasattr(self, "scheduler"):
            scheduler.cancel(self.scheduler)
    

def cache(
    timeout: Optional[float] = None,
):
    def decorator(func):
        cache = TimeoutCache(timeout)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            value = cache.get(key)
            if value is not None:
                return value
            value = func(*args, **kwargs)
            cache.set(key, value)
            return value

        return wrapper

    return decorator