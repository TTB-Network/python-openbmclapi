from core import const
from core import logger
from typing import Any, Callable
from importlib import import_module

TYPE: const.DataBaseType = const.DATABASETYPE
IMPORTS: dict[const.DataBaseType, str] = {
    const.DataBaseType.SQLITE: "sqlite"
}
METHODS: dict[str, Callable] = {}
def init():
    global METHODS
    logger.info(f"正在加载数据库中，当前类型为 [{TYPE.name}]")
    m = import_module(f"{__package__}.{TYPE.value}")
    for method in getattr(m, "__METHODS__"):
        METHODS[method] = getattr(m, method)
    connect()


def __wrapper(func):
    def decorator(*args, **kwargs):
        global METHODS
        if func.__name__ not in METHODS:
            raise AttributeError(f"Not found function: {func.__name__}")
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"{func.__name__}: {e} Exception SQL: {args}, {kwargs}")
    return decorator

@__wrapper
def connect():
    return METHODS["connect"]()

@__wrapper
def disconnect():
    return METHODS["disconnect"]()
    
@__wrapper
def execute(cmd: str, *params):
    return METHODS["execute"](cmd, *params)

@__wrapper
def executemany(*cmds: tuple[str, tuple[Any, ...]]):
    return METHODS["executemany"](*cmds)

@__wrapper
def query(cmd: str, *params) -> list[Any]:
    return METHODS["query"](cmd, *params)

@__wrapper
def queryAllData(cmd: str, *params) -> list[tuple]:
    return METHODS["queryAllData"](cmd, *params)

@__wrapper
def raw_execute(cmd: str, *params) -> None:
    return METHODS["raw_execute"](cmd, *params)

@__wrapper
def commit():
    return METHODS["commit"]()