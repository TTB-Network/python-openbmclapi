from pathlib import Path
from typing import Any
import yaml
import os

defaults = {
    "advanced.api_version": "1.11.0",
    "advanced.lang": "zh_cn",
    "advanced.debug": False,
    "advanced.retry": 5,
    "advanced.delay": 15,
    "advanced.sync_interval": 60,
    "cluster.base_url": "https://openbmclapi.bangbang93.com",
    "cluster.id": "",
    "cluster.secret": "",
    "cluster.host": "",
    "cluster.byoc": False,
    "cluster.public_port": 8080,
    "cluster.port": 8800,
    "storages": [{"type": "local", "path": "./cache"}],
    "advanced.paths.cert": "./cert/cert.pem",
    "advanced.paths.key": "./cert/key.pem",
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
        self.file.parent.mkdir(parents=True, exist_ok=True)
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
        for _, key in enumerate(keys[:-1]):
            if key not in dict_obj:
                dict_obj[key] = {}
            dict_obj = dict_obj[key]
        dict_obj[keys[-1]] = value


Config: CFG = CFG("./config/config.yml")
