from pathlib import Path
import sys
from typing import Any
import yaml
import os

defaults = {
    "advanced": {
        "lang": "zh_cn",
        "debug": False,
        "sync_interval": 600,
        "base_url": "https://openbmclapi.bangbang93.com",
        "dashboard_rank_clusters_url": "https://bd.bangbang93.com/openbmclapi/metric/rank",
        "threads": 128,
        "ssl_dir": ".ssl",
        "host": "",
        "ssl_cert": "",
        "ssl_key": "",
        "check_sign": True,
        "check_type": "size",
        "auto_sync_assets": True,
        "github_token": "",
        "measure_storage": False,
        "disallow_public_dashboard": False,
    },
    "web": {
        "port": -1,
        "public_port": 6543,
        "x_forwarded_for": 0,
        "backlog": 1024,
        "sockets": 8
    },
    "clusters": [
        {
            "id": "",
            "secret": "",
        }
    ],
    "storages": [
        {
            "type": "local", 
            "path": "./bmclapi",
            "weight": 0
        }
    ],
    "database": {
        "type": "sqlite",
        "url": "./database.db"
    },
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

class Const:
    @property
    def debug(self):
        return Config.get("advanced.debug", False)
    
    @property
    def base_url(self) -> str:
        return Config.get("advanced.base_url", "https://openbmclapi.bangbang93.com")
    
    @property
    def threads(self):
        return Config.get("advanced.threads", 128)
    
    @property
    def public_port(self):
        return os.environ.get("web.public_port", Config.get("web.public_port", 6543)) or 6543

    @property
    def port(self):
        return os.environ.get("web.port", Config.get("web.port", 0)) or 0
    
    @property
    def ssl_dir(self):
        return Config.get("advanced.ssl_dir", ".ssl")
    
    @property
    def host(self):
        return Config.get("advanced.host")
    
    @property
    def ssl_cert(self):
        return Config.get("advanced.ssl_cert")
    
    @property
    def ssl_key(self):
        return Config.get("advanced.ssl_key")
    
    @property
    def check_sign(self):
        return Config.get("advanced.check_sign") or True
    
    @property
    def check_type(self):
        return Config.get("advanced.check_type") or "size"
    
    @property
    def sync_interval(self):
        return max(Config.get("advanced.sync_interval", 600) or 600, 600)
    
    @property
    def xff(self):
        return Config.get("web.x_forwarded_for") or 0
    
    @property
    def auto_sync_assets(self):
        return bool(Config.get("advanced.auto_sync_assets", True))
    
    @property
    def github_token(self):
        return Config.get("advanced.github_token") or None
    
    @property
    def measure_storage(self) -> bool:
        return Config.get("advanced.measure_storage") or False

    @property
    def rank_clusters_url(self):
        return Config.get("advanced.dashboard_rank_clusters_url") or "https://bd.bangbang93.com/openbmclapi/metric/rank"
    
    @property
    def backlog(self):
        backlog = Config.get("web.backlog", 0)
        if not isinstance(backlog, int):
            backlog = 100
        return max(backlog, 100)
    
    @property
    def web_sockets(self):
        sockets = Config.get("web.sockets", 8)
        if not isinstance(sockets, int):
            sockets = 8
        return max(sockets, 1)
    
    @property
    def disallow_public_dashboard(self):
        return Config.get("advanced.disallow_public_dashboard", False) or False

const = Const()

VERSION = "3.5.1"
API_VERSION = "1.13.1"
USER_AGENT = f"openbmclapi/{API_VERSION} python-openbmclapi/{VERSION}"
PYTHON_VERSION = ".".join(map(str, (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)))