import importlib
import inspect
import os
import traceback
from types import ModuleType
from typing import Any
from pathlib import Path
from core import logger


class Plugin:
    def __init__(self, module: ModuleType) -> None:
        self._module = module
        self._version = getattr(self._module, "__VERSION__", None)
        self._author = getattr(self._module, "__AUTHOR__", None)
        self._name = getattr(self._module, "__NAME__", module.__name__)
        self._enable = False

    def _get_method(self, name):
        return getattr(self._module, name, None)

    async def _call_func(self, name: str, **kwargs) -> Any:
        func = self._get_method(name)
        if func is not None:
            if inspect.iscoroutinefunction(func):
                return await func(**kwargs)
            else:
                return func(**kwargs)
        return None

    async def init(self, **kwargs):
        return await self._call_func("init", **kwargs)

    async def enable(self, **kwargs):
        result = await self._call_func("enable", **kwargs)
        self._enable = True
        return result

    async def disable(self, **kwargs):
        self._enable = False
        return await self._call_func("disable", **kwargs)

    def get_version(self):
        return self._version

    def get_author(self):
        return self._author

    def get_name(self):
        return self._name


plugins: list[Plugin] = []


def load_plugins():
    logger.info('Attempting to load plugins...')
    dirlist = os.listdir("./plugins")
    for file in dirlist:
        load = None
        file_path = Path(f"./plugins/{file}")
        if os.path.isdir(file_path):
            if file[0] != '_':
                load = file
        elif os.path.isfile(file_path):
            if file[0] != '_' and file.endswith('.py'):
                load = file[:-3]
        if load:
            logger.debug(f"Loading plugins.{load}")
            try:
                plugin = Plugin(
                    importlib.import_module("plugins." + load)
                )
                logger.info(
                    f"Successfully loaded plugin [{plugin.get_name()}]! Version: [{plugin.get_version()}], Author: [{plugin.get_author()}]."
                )
                plugins.append(plugin)
            except:
                logger.error(traceback.format_exc())
                ...


def get_plugins():
    return plugins


def get_enable_plugins():
    return [plugin for plugin in plugins if plugin._enable]
