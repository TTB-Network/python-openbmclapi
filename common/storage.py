import asyncio
import hashlib
import random
import tempfile
from typing import Callable

from .database import get_database
from .env import env
from pathlib import Path

CACHE_DIR = Path(env.get("CACHE_DIR") or "./cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
RANDOM = random.SystemRandom()
        
    

db = get_database("storage")


class File:
    def __init__(
        self,
        digestmod: Callable[..., hashlib._Hash] = hashlib.sha256,
    ):
        self.digestmod = digestmod
        self._hash: hashlib._Hash = None # type: ignore
        self._tempfile: tempfile._TemporaryFileWrapper = None # type: ignore

    async def __aenter__(self):
        self._hash = self.digestmod()
        self._tempfile = tempfile.TemporaryFile(dir=CACHE_DIR, delete_on_close=False, delete=False)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._hash is not None:
            self._hash = None # type: ignore
        if self._tempfile is not None:
            self._tempfile.close()
            self._tempfile = None # type: ignore

    def write(self, data: bytes):
        self._hash.update(data)
        self._tempfile.write(data)

    def read(self):
        self._tempfile.seek(0)
        return self._tempfile.read()
    
    async def stream_read(self) -> asyncio.StreamReader:
        self._tempfile.seek(0)
        reader = asyncio.StreamReader()
        task = asyncio.create_task(self._tempfile.read(-1))
        return reader
