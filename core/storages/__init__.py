from collections import defaultdict
from dataclasses import dataclass
import inspect
from typing import Any, Optional, TypeVar


from core import logger

from .base import (
    iStorage,
    MeasureFile,
    File,
    iNetworkStorage
)
from .alist import (
    AlistStorage
)
from .webdav import (
    WebDavStorage
)
from .local import (
    LocalStorage
)
 

@dataclass
class Parameter:
    name: str
    type: type
    default: Any = inspect._empty

def init_storage(config: Any) -> Optional[iStorage]:
    if not isinstance(config, dict) or "type" not in config or config["type"] not in abstract_storages:
        return None
    try:
        abstract_storage = abstract_storages[config["type"]]
        args = abstract_storage_args[abstract_storage]
        params = {}
        for arg in args:
            if arg.name in config:
                params[arg.name] = config[arg.name]
            elif arg.default != inspect._empty:
                params[arg.name] = arg.default
        return abstract_storage(**params)
    except:
        logger.traceback()
        return None

abstract_storages: dict[str, type[iStorage]] = {}
abstract_storage_args: defaultdict[type[iStorage], list[Parameter]] = defaultdict(list)

T = TypeVar("T")

async def init():
    for istorage in (
        AlistStorage,
        WebDavStorage,
        LocalStorage
    ):
        if istorage.type == iStorage.type:
            continue
        abstract_storages[istorage.type] = istorage
        arg = inspect.getfullargspec(istorage.__init__)
        args = arg.args[1:]
        # defaults 默认的长度和位置都是从后往前数的，
        # 填充一些空的在前面
        defaults = [
            inspect._empty for _ in range(len(args) - len(arg.defaults or []))
        ]
        defaults.extend(arg.defaults or [])
        for idx, arg_name in enumerate(args):
            if arg_name == "self":
                continue
            abstract_storage_args[istorage].append(
                Parameter(
                    name=arg_name,
                    type=arg.annotations.get(arg_name, Any),
                    default=defaults[idx]
                )
            )

    logger.debug("Storage init complete")
    logger.debug(f"Found {len(abstract_storages)} storage types: {', '.join(abstract_storages.keys())}")