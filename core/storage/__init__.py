from collections import deque
from dataclasses import dataclass
from typing import Type

import anyio.abc


from ..abc import BMCLAPIFile
from .webdav import WebDavStorage
from .alist import AlistStorage
from .s3 import S3Storage
from .local import LocalStorage
from .minio import MinioStorage

from .abc import FileInfo, Storage
from ..logger import logger
from .. import utils
from tianxiu2b2t.anyio import concurrency

storages: dict[str, Type[Storage]] = {
    "local": LocalStorage,
    "alist": AlistStorage,
    "webdav": WebDavStorage,
    #"s3": S3Storage,
    "minio": MinioStorage
}

@dataclass
class StorageTypeCount:
    file: int = 0
    alist: int = 0
    webdav: int = 0
    s3: int = 0

    @property
    def type(self):
        res = []
        if self.file > 0:
            res.append("file")
        if self.alist > 0:
            res.append("alist")
        if self.webdav > 0:
            res.append("webdav")
        if self.s3 > 0:
            res.append("s3")
        return "+".join(res)

class StorageManager:
    def __init__(
        self
    ):
        self._storages: deque[Storage] = deque()
        self._weight_storages: deque[Storage] = deque()
        self._online_storages: deque[Storage] = deque()
        self._status = False
    
    @property
    def get_storage_type(self):
        res = StorageTypeCount()
        for storage in self._storages:
            if isinstance(storage, LocalStorage):
                res.file += 1
            elif isinstance(storage, AlistStorage):
                res.alist += 1
            elif isinstance(storage, WebDavStorage):
                res.webdav += 1
            elif isinstance(storage, S3Storage):
                res.s3 += 1
            elif isinstance(storage, MinioStorage):
                res.s3 += 1
        return res
        

    def add_storage(
        self,
        name: str,
        path: str,
        type: str,
        weight: int = 0,
        **kwargs
    ):
        if type not in storages:
            logger.error(f"Storage type {type} not found")
            return
        storage = storages[type](name, path, weight, **kwargs)
        self._storages.append(storage)
        
        if storage.weight >= 0:
            self._weight_storages.append(storage)
    
    @property
    def count(self):
        return len(self._storages)
    
    @property
    def storages(self):
        return self._storages
    
    async def setup(
        self,
        task_group: anyio.abc.TaskGroup
    ):
        await concurrency.gather(*(
            storage.setup(task_group)
            for storage in self._storages
        ))

        @utils.event.callback("storage.status")
        async def _(data: tuple[Storage, bool]):
            c, status = data
            if status and c not in self._online_storages:
                self._online_storages.append(c)
            elif not status and c in self._online_storages:
                self._online_storages.remove(c)
            if self._status and len(self._online_storages) == 0:
                utils.event.emit("storage_disable")
            elif not self._status and len(self._online_storages) > 0:
                utils.event.emit("storage_enable")
            
            self._status = len(self._online_storages) > 0

    def get_weight_storage(self):
        c = None
        back_storages: list[Storage] = []
        for storage in self._weight_storages:
            if not storage.online:
                continue
            if storage.weight < 0:
                back_storages.append(storage)
                continue
            if storage.current_weight < storage.weight:
                c = storage
                storage.current_weight += 1
                break
            else:
                c = storage
        if c is None and len(back_storages) > 0:
            c = back_storages.pop()
        return c
            

class CheckStorage:
    def __init__(
        self,
        storage: Storage,
    ):
        self.storage = storage
        self.files: dict[str, FileInfo] = {}
        self.missing_files: set[BMCLAPIFile] = set()

    async def get_missing_files(self, bmclapi_files: set[BMCLAPIFile], muitlpbar: utils.MultiTQDM):

        for file in await self.storage.list_download_files(muitlpbar):
            self.files[file.name] = file
        muitlpbar.update(1)

        # start check
        # with concurreny
        async with anyio.create_task_group() as task_group:
            # spilt bmclapi_files into 10 parts
            for files in utils.split_workload(list(bmclapi_files), 10):
                task_group.start_soon(self._check, files)

        return self.missing_files

    async def _check(
        self,
        files: list[BMCLAPIFile]
    ):
        for file in files:
            if await self._check_file(file):
                continue
            self.missing_files.add(file)


    async def _check_file(self, file: BMCLAPIFile):
        # default use check exists + size
        return await self._check_file_size(file)
        
    async def _check_file_size(self, file: BMCLAPIFile):
        return await self._check_file_exists(file) and self.files[file.hash].size == file.size
        
    async def _check_file_exists(self, file: BMCLAPIFile):
        return file.hash in self.files
            

