from pathlib import Path
import yaml
import os
from core.logger import logger

defaults = {
    "cluster_id": "",
    "cluster_secret": "",
    "max_download": 64,
    "port": 8800,
    "public_port": None,
    "public_host": "",
    "byoc": False,
    "timeout": 30,
    "min_rate_timestamp": 1000,
    "min_rate": 500,
    "request_buffer": 8192,
    "io_buffer": 16777216,
    "server_name": "TTB-Network"
}

class CFG:
    def __init__(self, path: str) -> None:
        self.file = Path(path)
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
        return value

    def write(self, key, value):
        self.cfg[key] = value
        with open(self.file, "w", encoding="utf-8") as f:
            yaml.dump(data=self.cfg, stream=f, allow_unicode=True)

Config: CFG = CFG("./config/config.yaml")







