from datetime import timedelta
import datetime
import io
import tempfile
import time
from typing import Optional
import urllib.parse as urlparse
import aiohttp
import anyio.abc

from ..abc import ResponseFile, ResponseFileMemory, ResponseFileRemote, ResponseFileNotFound
from ..utils import UnboundTTLCache
from ..logger import logger

from .abc import CPath, FileInfo, Storage
from miniopy_async import Minio
from miniopy_async.api import BaseURL, presign_v4
from miniopy_async.datatypes import Object
from tianxiu2b2t import units


class MinioStorage(Storage):
    type = "minio"
    def __init__(
        self,
        name: str,
        path: str,
        weight: int,
        access_key: str,
        secret_key: str,
        endpoint: str,
        bucket: str,
        **kwargs
    ):
        super().__init__(name, path, weight, **kwargs)

        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = kwargs.get("region", "pyoba")
        self.custom_host = kwargs.get("custom_host")
        self.public_endpoint = kwargs.get("public_endpoint")
    
        url = urlparse.urlparse(self.endpoint)
        self._cache: UnboundTTLCache[str, ResponseFile] = UnboundTTLCache(
            maxsize=self.cache_size, 
            ttl=self.cache_ttl
        )

        self.minio = Minio(
            endpoint=url.netloc,
            access_key=access_key,
            secret_key=secret_key,
            region=self.region,
            secure=url.scheme == "https",
        )

    async def setup(
        self,
        task_group: anyio.abc.TaskGroup
    ):
        await super().setup(task_group)

        if not await self.minio.bucket_exists(self.bucket):
            await self.minio.make_bucket(
                self.bucket,
                location=self.region
            )

        task_group.start_soon(self._check)

    async def list_files(
        self,
        path: str
    ) -> list[FileInfo]:
        root = self.path / path
        res = []
        # only files
        async for obj in self.minio.list_objects(
            self.bucket, 
            prefix=str(root)[1:],
            recursive=True
        ):
            if not isinstance(obj, Object):
                continue
            res.append(FileInfo(
                name=CPath(obj.object_name).name,
                size=int(obj.size or 0),
                path=str(obj.object_name),
            ))
        return res
    
    async def upload(
        self,
        path: str,
        data: io.BytesIO,
        size: int
    ):
        root = self.path / path
        
        await self.minio.put_object(
            self.bucket,
            str(root)[1:],
            data.getbuffer(),
            size
        )
        return True

    async def _check(
        self,
    ):
        file = self.get_py_check_path()
        while 1:
            try:
                data = str(time.perf_counter_ns())
                await self.minio.put_object(
                    self.bucket,
                    file.name,
                    io.BytesIO(data.encode("utf-8")),
                    len(data)
                )
                self.online = True
            except:
                self.online = False
                logger.traceback()
            finally:
                self.emit_status()
                await anyio.sleep(60)
        
    async def get_file(self, path: str) -> ResponseFile:
        cpath = str(self.path / path)
        # get file info
        file = self._cache.get(cpath)
        if file is not None:
            return file
        try:
            stat = await self.minio.stat_object(
                self.bucket,
                cpath[1:],
            )
        except:
            stat = Object(
                bucket_name=self.bucket,
                object_name=cpath[1:],
            )
        if stat.size == 0:
            file = ResponseFileMemory(
                b"",
                0
            )
        elif self.custom_host is not None:
            file = ResponseFileRemote(
                f"{self.custom_host}/{self.bucket}{cpath}",
                int(stat.size or 0),
            )
        elif self.public_endpoint is not None:
            url = await get_presigned_url(
                self.minio,
                "GET",
                self.bucket,
                cpath[1:],
                region=self.region,
                change_host=self.public_endpoint,
            )
            file = ResponseFileRemote(
                url,
                int(stat.size or 0),
            )
        else:
            async with aiohttp.ClientSession() as session:
                async with (await self.minio.get_object(
                    self.bucket,
                    cpath[1:],
                    session
                )) as resp:
                    file = ResponseFileMemory(
                        await resp.read(),
                        int(stat.size or 0),
                    )
        self._cache[cpath] = file
        return file

    async def check_measure(self, size: int) -> bool:
        cpath = str(self.path / "measure" / size)
        stat = await self.minio.stat_object(
            self.bucket,
            cpath[1:],
        )
        return stat.size == size * 1024 * 1024

async def get_presigned_url(
    minio: Minio,
    method: str,
    bucket_name: str,
    object_name: str,
    region: Optional[str] = None,
    expires: timedelta = timedelta(days=7),
    request_date: Optional[datetime.datetime] = None,
    extra_query_params=None,
    change_host=None,
):
    if expires.total_seconds() < 1 or expires.total_seconds() > 604800:
        raise ValueError("expires must be between 1 second to 7 days")
    region = region or await minio._get_region(bucket_name, None)
    query_params = extra_query_params or {}
    creds = minio._provider.retrieve() if minio._provider else None
    if creds and creds.session_token:
        query_params["X-Amz-Security-Token"] = creds.session_token
    url = None
    if change_host:
        url = BaseURL(
            change_host,
            region,
        ).build(
            method,
            region,
            bucket_name=bucket_name,
            object_name=object_name,
            query_params=query_params,
        )
    else:
        url = minio._base_url.build(
            method,
            region,
            bucket_name=bucket_name,
            object_name=object_name,
            query_params=query_params,
        )
    if creds:
        url = presign_v4(
            method,
            url,
            region,
            creds,
            request_date or datetime.datetime.now(datetime.UTC),
            int(expires.total_seconds()),
        )
    return urlparse.urlunsplit(url)