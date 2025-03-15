import importlib
from typing import Any
from .abc import DataBase


loaders = {
    "local": "SqliteDB",
    "mongo": "MongoDB",
    "memory": "MemoryDataBase"
}

db = None

async def init(
    config: dict[str, Any]
):
    global db
    type = config.get('type', 'memory')
    module = importlib.import_module(f'.{type}', __package__)
    instance = getattr(module, loaders[type])
    database_name = config.get('database_name', 'pyoba')
    db = instance(
        database_name=database_name,
        **config
    )


def get_db() -> DataBase:
    assert db is not None, 'Database not initialized'
    return db