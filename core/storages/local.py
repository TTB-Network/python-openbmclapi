import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import os
from pathlib import Path
from typing import Any, Optional

import aiofiles

from .base import DOWNLOAD_DIR, File, iStorage, CollectionFile
from core.utils import WrapperTQDM


class LocalStorage(iStorage):
    type = "local"

    def __init__(self, path: str, weight: int = 0, list_concurrent: int = 32, name: Optional[str] = None):
        super().__init__(path, weight, list_concurrent, name)
        self.async_executor = ThreadPoolExecutor(max_workers=list_concurrent)

    @staticmethod
    def from_config(config: dict[str, Any]):
        return LocalStorage(config["path"], config.get("weight", 0), config.get("list_concurrent", 32), config.get("name"))

    @property
    def unique_id(self):
        return hashlib.md5(f"{self.type},{self.path}".encode("utf-8")).hexdigest()

    async def _to_coroutine(self, func, *args, **kwargs):
        return await asyncio.get_event_loop().run_in_executor(self.async_executor, func, *args, **kwargs)

    async def list_files(self, pbar: WrapperTQDM) -> set[File]:
        def get_files(root_id: str):
            root = os.path.join(str(self.path / DOWNLOAD_DIR), root_id)
            if not os.path.isdir(root):
                pbar.update(1)
                return deque()
            results: deque[File] = deque()
            for file in os.listdir(root):
                path = os.path.join(root, file)
                if not os.path.isfile(path):
                    continue
                results.append(File(
                    file,
                    os.path.getsize(path),
                    os.path.getmtime(path),
                    file
                ))
            pbar.update(1)
            return results

        return set().union(*await asyncio.gather(*[self._to_coroutine(get_files, root_id) for root_id in os.listdir(str(self.path))]))
            
    
    async def write_file(self, file: CollectionFile, content: io.BytesIO):
        path = self.get_path(file)

        parent = path.parent
        parent_path = Path(str(parent))
        parent_path.mkdir(parents=True, exist_ok=True)
        file_path = Path(str(path))
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(await self._to_coroutine(content.read))

    async def read_file(self, file: File) -> io.BytesIO:
        path = self.get_path(file)
        with open(Path(str(path)), "rb") as f:
            return io.BytesIO(await self._to_coroutine(f.read))
        
    async def delete_file(self, file: CollectionFile):
        path = self.get_path(file)
        os.remove(Path(str(path)))

    async def exists(self, file: CollectionFile) -> bool:
        path = self.get_path(file)
        return os.path.isfile(Path(str(path)))
    

    async def get_size(self, file: CollectionFile) -> int:
        path = self.get_path(file)
        return os.path.getsize(Path(str(path)))
    
    async def get_mtime(self, file: CollectionFile) -> float:
        path = self.get_path(file)
        return os.path.getmtime(Path(str(path)))
