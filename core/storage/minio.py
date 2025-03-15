import io
import tempfile
import time
import urllib.parse as urlparse
import aiohttp
import anyio.abc

from ..abc import ResponseFile, ResponseFileMemory, ResponseFileRemote, ResponseFileNotFound
from ..utils import UnboundTTLCache
from ..logger import logger

from .abc import CPath, FileInfo, Storage
from miniopy_async import Minio
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
        super().__init__(name, path, weight)

        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = kwargs.get("region", "pyoba")
        self.custom_host = kwargs.get("custom_host")
        self.public_endpoint = kwargs.get("public_endpoint")
    
        url = urlparse.urlparse(self.endpoint)
        
        self._cache_files: UnboundTTLCache[str, FileInfo] = UnboundTTLCache(
            maxsize=int(units.parse_number_units(kwargs.get("cache_size", "10000"))), 
            ttl=units.parse_time_units(kwargs.get("cache_files_ttl", "120s"))
        )
        self._cache: UnboundTTLCache[str, ResponseFile] = UnboundTTLCache(
            maxsize=int(units.parse_number_units(kwargs.get("cache_size", "10000"))), 
            ttl=units.parse_time_units(kwargs.get("cache_ttl", "5m"))
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
        tmp_file: tempfile._TemporaryFileWrapper,
        size: int
    ):
        root = self.path / path
        
        await self.minio.put_object(
            self.bucket,
            str(root)[1:],
            tmp_file,
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
        cname = str((self.path / path).name)
        cpath = str(self.path / path)
        # get file info
        file = self._cache.get(cpath)
        if file is not None:
            return file
        async with aiohttp.ClientSession() as session:
            fileinfo = self._cache_files.get(cpath)
            resp = None
            if not fileinfo:
                resp = await self.minio.get_object(
                    self.bucket,
                    cpath[1:],
                    session,
                )
                fileinfo = FileInfo(
                    name=cname,
                    size=int(resp.headers.get("content-length") or 0),
                    path=cpath,
                )
                self._cache_files[cpath] = fileinfo
            if self.custom_host is None and self.public_endpoint is None:
                if resp is None:
                    resp = await self.minio.get_object(
                        self.bucket,
                        cpath[1:],
                        session,
                    )
                file = ResponseFileMemory(
                    data=await resp.read(),
                    size=fileinfo.size
                )
                resp.release()
                resp = None
        if file is not None:
            self._cache[cpath] = file
            return file
        if self.custom_host is not None:
            file = ResponseFileRemote(
                f"{self.custom_host}{cpath}",
                fileinfo.size
            )
        elif self.public_endpoint is not None:
            url = await self.minio.get_presigned_url(
                "GET",
                self.bucket,
                cpath[1:],
            )
            urlobj = urlparse.urlparse(url)
            # replace host
            pub_urlobj = urlparse.urlparse(self.public_endpoint)
            url: str = urlparse.urlunparse(
                (
                    pub_urlobj.scheme or urlobj.scheme,
                    pub_urlobj.netloc or urlobj.netloc,
                    urlobj.path,
                    urlobj.params,
                    urlobj.query,
                    urlobj.fragment,
                )
            )
            file = ResponseFileRemote(
                url,
                fileinfo.size
            )
        if file is None:
            return ResponseFileNotFound()
        self._cache[cpath] = file
        return file
        
        
    