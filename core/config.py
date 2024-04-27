from pathlib import Path
import random
import string
from typing import Any
import yaml
import os

defaults = {
    "cluster.id": "",
    "cluster.secret": "",
    "cluster.public_port": 8800,
    "cluster.public_host": "",
    "cluster.byoc": False,
    "cluster.enable": True,
    "cluster.timeout.enable": 120,
    "cluster.timeout.keepalive": 300,
    "cluster.reconnect.delay": 60,
    "cluster.reconnect.retry": -1,
    "cache.buffer": 536870912,
    "cache.time": 1800,
    "cache.check": 360,
    "cache.enable": True,
    "web.server_name": "TTB-Network",
    "web.x_forwarded_for": 0,
    "web.port": 8080,
    "web.ssl_port": 8800,
    "web.force_ssl": False,
    "advanced.timeout": 30,
    "advanced.min_rate_timestamp": 1000,
    "advanced.min_rate": 500,
    "advanced.file_check_mode": "size",
    "advanced.request_buffer": 8192,
    "advanced.download_threads": 64,
    "advanced.io_buffer": 16777216,
    "advanced.header_bytes": 4096,
    "advanced.url": "https://openbmclapi.bangbang93.com/",
    "advanced.skip_sign": False,
    "advanced.debug": False,
    "advanced.language": "zh_cn",
    "advanced.auto_update": False,
    "dashboard.username": "admin",
    "dashboard.websocket": True,
    "dashboard.password": ''.join(random.choices(string.ascii_letters + string.digits, k=6)),
    "storages": {"bmclapi": {"type": "file", "path": "./bmclapi", "width": 0}},
}


class CFG:
    def __init__(self, path: str) -> None:
        self.file = Path(path)
        self.cfg = {}
        if self.file.exists():
            self.load()
        else:
            for key, value in defaults.items():
                self.set(key, value)
            print(f"[Config] Dashboard password: {self.get('dashboard.password')}.")

    def load(self):
        with open(self.file, "r", encoding="utf-8") as f:
            self.cfg = yaml.load(f.read(), Loader=yaml.FullLoader) or {}

    def get(self, key: str, def_: Any = None) -> Any:
        value = os.environ.get(key, None) or self._get_value(self.cfg, key.split("."))
        if value is None and def_ is None:
            print(f"[Config] {key} is not set, does it exist?")
            if key in defaults:
                value = defaults.get(key, None)
                if value is not None:
                    self.set(key, value)
        return value

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

if not os.path.exists("./config"):
    print("The config dir is not exists.")
    os.mkdir("./config")
Config: CFG = CFG("./config/config.yml")
