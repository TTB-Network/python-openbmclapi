import os
from pathlib import Path
import traceback
from typing import Any
import yaml

class Config:
    def __init__(self):
        self._data = {}
        self.load()

    def load(self):
        try:
            with open(ROOT_PATH / "config" / "config.yml", "r") as f:
                self._data = yaml.safe_load(f) or {}
        except:
            print("[Config] Failed to load config.yml")
            print(traceback.format_exc())

    def save(self):
        with open(ROOT_PATH / "config" / "config.yml", "w") as f:
            yaml.dump(self._data, f)

    def _get_keys(self, key: str):
        return key.split(".")

    def get(self, key: str, default = None) -> Any:
        val = os.getenv(key) or self._get_value(self._data, self._get_keys(key))
        if val is None:
            print(f"[Config] Key '{key}' is not set?")
            if key in DEFAULT_CONFIG:
                self.set(key, DEFAULT_CONFIG[key])
                val = DEFAULT_CONFIG[key]
                self.save()
            else:
                val = default
        return val
    
    def _get_value(self, dict_obj, keys):
        for key in keys:
            if key in dict_obj:
                dict_obj = dict_obj[key]
            else:
                return None
        return dict_obj

    def set(self, key: str, value: Any):
        keys = self._get_keys(key)
        data = self._data
        for k in keys[:-1]:
            if not isinstance(data, dict) or k not in data:
                data[k] = {}
            data = data[k] # type: ignore
        data[keys[-1]] = value
        self.save()

    @property
    def web_port(self) -> int:
        return int(self.get("web.port"))
    
    @property
    def web_public_port(self) -> int:
        return int(self.get("web.public_port"))
    
    @property
    def base_url(self) -> str:
        return self.get("advanced.base_url", "https://openbmclapi.bangbang93.com")
        
    @property
    def host(self):
        return self.get("advanced.host") or ""
    
    @property
    def access_log(self):
        return self.get("advanced.access_log") or False

API_VERSION = "1.13.1"
VERSION = "4.0.0-alpha"
PROJECT = "PythonOpenBMCLAPI"
USER_AGENT = f"openbmclapi-cluster/{API_VERSION} {PROJECT}/{VERSION}"
ROOT_PATH = Path(__file__).parent.parent
DEFAULT_CONFIG = {
    "advanced.locale": "zh_cn",
    "advanced.debug": False,
    "advanced.access_log": False,
    "advanced.host": "",
    "web.port": 6543,
    "web.public_port": 6543,
    "web.proxy": False,
    "cert.dir": ".ssl",
    "cert.key": None,
    "cert.cert": None,
}

cfg = Config()

DEBUG = bool(cfg.get("advanced.debug")) or False 