from core.types import Storage
from core.storages.local import LocalStorage
from core.config import Config
from typing import List


def getStorages() -> List[Storage]:
    config = Config.get("storages")
    storages = []
    for storage in config:
        if storage["type"] == "local":
            storages.append(LocalStorage(path=storage["path"]))
    return storages
