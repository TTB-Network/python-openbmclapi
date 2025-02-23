import inspect
from io import BytesIO
import tempfile
import time
from typing import Any
import aioboto3.session
import anyio.abc
import anyio.to_thread
import aioboto3
import urllib.parse as urlparse

from core import logger
from . import abc
import cachetools

class S3ResponseMetadata:
    def __init__(
        self,
        data: dict
    ):
        self.request_id = data.get("RequestId")
        self.host_id = data.get("HostId")
        self.http_status_code = data.get("HttpStatusCode")
        self.http_headers = data.get("HttpHeaders")

    def __repr__(
        self
    ) -> str:
        return f"S3ResponseMetadata(request_id={self.request_id}, host_id={self.host_id}, http_status_code={self.http_status_code}, http_headers={self.http_headers})"

class S3Response:
    def __init__(
        self,
        data: dict
    ):
        self.raw_data = data
        self.metadata = S3ResponseMetadata(data.get("ResponseMetadata", {}))

    def __repr__(
        self
    ) -> str:
        return f"S3Response(metadata={self.metadata}, data={self.raw_data})"

class S3Storage(abc.Storage):
    type = "s3"
    def __init__(
        self,
        name: str,
        path: str,
        weight: int,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        **kwargs
    ):
        super().__init__(name, path, weight)
        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = kwargs.get("region")
        self.custom_s3_host = kwargs.get("custom_s3_host", "")
        self.public_endpoint = kwargs.get("public_endpoint", "")
        self.session = aioboto3.Session()
        self._cache: cachetools.TTLCache[str, abc.ResponseFile] = cachetools.TTLCache(maxsize=10000, ttl=60)
        self._cache_files: cachetools.TTLCache[str, abc.FileInfo] = cachetools.TTLCache(maxsize=10000, ttl=60)
        self._config = {
            "endpoint_url": self.endpoint,
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
        }
        if self.region:
            self._config["region_name"] = self.region
            
        
    async def setup(
        self,
        task_group: anyio.abc.TaskGroup
    ):
        await super().setup(task_group)

        self.task_group.start_soon(self._check)

    async def list_files(
        self,
        path: str
    ) -> list[abc.FileInfo]:
        p = str(self.path / path)
        res = []
        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        ) as client: # type: ignore
            continuation_token = None
            while True:
                kwargs = {
                    "Bucket": self.bucket,
                    "Prefix": p[1:],
                    #"Delimiter": "/",  # 使用分隔符来模拟文件夹结构
                    #"MaxKeys": 1000
                }
                if continuation_token:
                    kwargs["ContinuationToken"] = continuation_token

                response = await client.list_objects_v2(**kwargs)
                contents = response.get("Contents", [])
                for content in contents:
                    file_path = f"/{content['Key']}"
                    if "/" in file_path:
                        file_name = file_path.rsplit("/", 1)[1]
                    else:
                        file_name = file_path[1:]
                    res.append(abc.FileInfo(
                        name=file_name,
                        size=content["Size"],
                        path=f'/{content["Key"]}',
                    ))

                #res.extend(response.get("Contents", []))  # 添加文件
                #res.extend(response.get("CommonPrefixes", []))  # 添加子目录

                if "NextContinuationToken" not in response:
                    break
                continuation_token = response["NextContinuationToken"]
        return res


    async def upload(
        self,
        path: str,
        tmp_file: tempfile._TemporaryFileWrapper
    ):
        async with self.session.resource(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        ) as resource:
            bucket = await resource.Bucket(self.bucket)
            obj = await bucket.Object(str(self.path / path))
            await obj.upload_fileobj(tmp_file)
        return True


    async def _check(
        self,
    ):
        while 1:
            try:
                async with self.session.resource(
                    "s3",
                    endpoint_url=self.endpoint,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region
                ) as resource:
                    bucket = await resource.Bucket(self.bucket)
                    obj = await bucket.Object(str(self.path / ".py_check"))
                    await obj.upload_fileobj(BytesIO(str(time.perf_counter_ns()).encode()))
                    await obj.delete()
                self.online = True
            except:
                self.online = False
                logger.traceback()
            finally:
                self.emit_status()
                await anyio.sleep(60)
    
    async def get_response_file(self, hash: str) -> abc.ResponseFile:
        cpath = str(self.path / "download" / hash[:2] / hash)
        fileinfo = self._cache_files.get(hash)

        if fileinfo is None:
            async with self.session.resource(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            ) as resource:
                bucket = await resource.Bucket(self.bucket)
                obj = await bucket.Object(cpath)
                info = await obj.get()
                fileinfo = abc.FileInfo(
                    name=hash,
                    size=info["ContentLength"],
                    path=cpath
                )
                self._cache_files[hash] = fileinfo
        
        if fileinfo is None:
            return abc.ResponseFileNotFound()

        if self.custom_s3_host:
            return abc.ResponseFileRemote(
                f"{self.custom_s3_host}{cpath}",
                fileinfo.size
            )
        if self.public_endpoint:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            ) as client: # type: ignore
                url = await client.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={
                        "Bucket": self.bucket,
                        "Key": cpath[1:]
                    }
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
                return abc.ResponseFileRemote(
                    url,
                    fileinfo.size
                )
        async with self.session.resource(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        ) as resource:
            bucket = await resource.Bucket(self.bucket)
            obj = await bucket.Object(cpath)
            # read data
            content = await obj.get()
            size = content['ContentLength']
            return abc.ResponseFileMemory(
                await content['Body'].read(),
                size
            )
            