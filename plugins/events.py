# do not load...
from abc import ABCMeta
from collections import defaultdict
import inspect
import time
from typing import Any, Awaitable, Callable, Union

Function = Callable[["Event"], Union[Awaitable[Any], Any]]
registry_handlers: defaultdict[int, set[Function]] = defaultdict(lambda: set())

class Event(metaclass=ABCMeta):
    def __init__(self) -> None:
        self.__event_name = self.__class__.__name__
        self.__create_at = time.time()
    def get_event_name(self):
        return self.__event_name
    def get_create_at(self):
        return self.__create_at
    def __repr__(self) -> str:
        return f"<{self.get_event_name()}, create_at={self.get_create_at()}>"
    
class ClusterEnableEvent(Event):
    ...

class ClusterDisableEvent(Event):
    ...

class ClusterEnableErrorEvent(Event):
    def __init__(self, error: str) -> None:
        super().__init__()
        self.__error = error
    def get_error(self):
        return self.__error
    

def event(func: Function, priority: int = 0):
    global registry_handlers
    async def wrapper(*args, **kwargs):
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    registry_handlers[priority].add(wrapper)
    return wrapper