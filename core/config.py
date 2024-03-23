from pathlib import Path
from typing import Any, Optional
import yaml
import os
from core.logger import logger

defaults = {
    "cluster.id": "",
    "cluster.secert": "",
    "cluster.public_port": None,
    "cluster.public_host": "",
    "cluster.byoc": False,
    "download.threads": 64,
    "web.server_name": "TTB-Network",
    "web.port": 80,
    "web.ssl_port": 0,
    "web.force_ssl": False,
    "advanced.timeout": 30,
    "advanced.min_rate_timestamp": 1000,
    "advanced.min_rate": 500,
    "advanced.request_buffer": 8192,
    "advanced.io_buffer": 16777216,
}


class CFG:
    def __init__(self, path: str) -> None:
        self.file = Path(path)
        logger.debug(f"Load config: {self.file.absolute()}")
        self.cfg = {}
        if self.file.exists():
            self.load()
    def load(self):
        with open(self.file, "r", encoding="utf-8") as f:
            self.cfg = yaml.load(f.read(), Loader=yaml.FullLoader) or {}
    def get(self, key: str, def_: Any = None) -> Any:
        value = self._get_value(self.cfg, key.split(".")) or (defaults[key] if key in defaults else def_)
        self.set(key, value)
        return value
    def get_integer(self, key: str, def_: Optional[int] = None) -> Any:
        return self.get(key, def_) or 0
    def get_boolean(self, key: str, def_: Optional[int] = None) -> Any:
        val = self.get(key, def_) or "false"
        return val.lower() == "true"
    def set(self, key: str, value: Any):
        self._set_value(self.cfg, key.split("."), value)  
        self.save()  
    def save(self):
        with open(self.file, "w", encoding="utf-8") as f:
            yaml.dump(data=self.cfg, stream=f, allow_unicode=True)
    def _get_value(self, dict_obj, keys):  
        for key in keys:  
            if key in dict_obj:  
                dict_obj = dict_obj[key]  
            else:  
                return None  
        return dict_obj  
  
    def _set_value(self, dict_obj, keys, value):  
        for i, key in enumerate(keys[:-1]):  
            if key not in dict_obj:  
                dict_obj[key] = {}  
            dict_obj = dict_obj[key]  
        dict_obj[keys[-1]] = value  

"""class CFG:
    def __init__(self, path: str) -> None:
        self.file = Path(path)
        logger.debug(f"Load config: {self.file.absolute()}")
        self.cfg = {}
        if self.file.exists():
            self.load()

    def load(self):
        with open(self.file, "r", encoding="utf-8") as f:
            self.cfg = yaml.load(f.read(), Loader=yaml.FullLoader) or {}

    def get(self, key):
        value = self.cfg.get(key, None)
        if value is None or value == "":
            value = os.environ.get(key)
            if value:
                return value
            logger.warn(f"{key} is not set! Does it exist?")
            self.write(key, defaults[key])
        return value or (defaults[key] if key in defaults else value)

    def write(self, key, value):
        self.cfg[key] = value
        with open(self.file, "w", encoding="utf-8") as f:
            yaml.dump(data=self.cfg, stream=f, allow_unicode=True)
"""

Config: CFG = CFG("./config/config.yml")
