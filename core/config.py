import datetime
import os
from pathlib import Path
import traceback
from typing import Any
import yaml

from tianxiu2b2t import units

class Config:
    def __init__(self):
        self._data = {}
        self._key_noexists: set[str] = set() 
        self.load()

    def load(self):
        try:
            file = ROOT_PATH / "config" / "config.yml"
            if not file.exists():
                return
            with open(file, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
        except:
            print("[Config] Failed to load config.yml")
            print(traceback.format_exc())
            exit(520)

    def save(self):
        with open(ROOT_PATH / "config" / "config.yml", "w", encoding="utf-8") as f:
            yaml.dump(self._data, f)

    def _get_keys(self, key: str):
        return key.split(".")

    def get(self, key: str, default = None) -> Any:
        val = os.getenv(key) or self._get_value(self._data, self._get_keys(key))
        if val is None:
            if key in DEFAULT_CONFIG:
                self.set(key, DEFAULT_CONFIG[key])
                val = DEFAULT_CONFIG[key]
                self.save()
            else:
                if key not in self._key_noexists:
                    self._key_noexists.add(key)
                    print(f"[Config] Key '{key}' is not set?")
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
    def bd_url(self) -> str:
        return self.get("advanced.bd_url", "https://bd.bangbang93.com")
        
    @property
    def host(self):
        return self.get("advanced.host") or ""
    
    @property
    def access_log(self):
        return self.get("advanced.access_log") or False
    
    @property
    def storage_measure(self) -> bool:
        return self.get("advanced.storage_measure") or False
    
    @property
    def concurrency_enable_cluster(self) -> bool:
        return self.get("advanced.concurrency_enable_cluster") or False
    
    @property
    def cluster_up_failed_times(self) -> int:
        return self.get("advanced.cluster_up_failed_times") or 90
    
    @property
    def cluster_up_failed_interval(self) -> datetime.timedelta: # 24 hours
        return datetime.timedelta(seconds=units.parse_time_units(self.get("advanced.cluster_up_failed_interval") or "24h") / 1e9)


API_VERSION = "1.13.1"
VERSION = "4.0.12"
PROJECT = "PythonOpenBMCLAPI"
USER_AGENT = f"openbmclapi-cluster/{API_VERSION} {PROJECT}/{VERSION}"
ROOT_PATH = Path(__file__).parent.parent
ROOT = ROOT_PATH / "config"
DEFAULT_CONFIG = {
    "advanced.locale": "zh_cn",
    "advanced.debug": False,
    "advanced.access_log": False,
    "advanced.host": "",
    "advanced.concurrency_enable_cluster": False,
    "web.port": 6543,
    "web.public_port": 6543,
    "web.proxy": False,
    "cert.dir": ".ssl",
    "cert.key": None,
    "cert.cert": None,
}

ROOT.mkdir(exist_ok=True, parents=True)

cfg = Config()

DEBUG = bool(cfg.get("advanced.debug")) or False 