from pathlib import Path
from typing import Any, Optional
import yaml
import os
from core.logger import logger

defaults = {
    "cluster.id": "",
    "cluster.secret": "",
    "cluster.public_port": 8800,
    "cluster.public_host": "",
    "cluster.byoc": False,
    "download.threads": 64,
    "web.server_name": "TTB-Network",
    "web.port": 8080,
    "web.ssl_port": 8800,
    "web.force_ssl": False,
    "advanced.timeout": 30,
    "advanced.min_rate_timestamp": 1000,
    "advanced.min_rate": 500,
    "advanced.request_buffer": 8192,
    "advanced.io_buffer": 16777216,
    "advanced.header_bytes": 4096,
}


class CFG:
    def __init__(self, path: str) -> None:
        self.file = Path(path)
        logger.debug(f"Loading config: {self.file.absolute()}.")
        self.cfg = {}
        if self.file.exists():
            self.load()

    def load(self):
        with open(self.file, "r", encoding="utf-8") as f:
            self.cfg = yaml.load(f.read(), Loader=yaml.FullLoader) or {}

    def get(self, key: str, def_: Any = None) -> Any:
        value = (
            os.environ.get(key)
            or self._get_value(self.cfg, key.split("."))  
        )
        if value == None or value == "":
            logger.warn(f"{key} is not set! Does it exist?")
            self.set(key, defaults[key] or def_)
            value = defaults[key] or def_
        return value if value else defaults[key]

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


Config: CFG = CFG("./config/config.yml")
