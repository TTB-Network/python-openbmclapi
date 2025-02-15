import tempfile
import time
import aioboto3.session
import anyio.abc
import anyio.to_thread
import aioboto3
import urllib.parse as urlparse
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
        self.custom_s3_host = kwargs.get("custom_s3_host", "")
        self.public_endpoint = kwargs.get("public_endpoint", "")
        self.session = aioboto3.Session()
        self.list_lock = anyio.Lock()
        self.cache_list_bucket: dict[str, abc.FileInfo] = {}
        self.last_cache: float = 0
        
    async def setup(
        self,
        task_group: anyio.abc.TaskGroup
    ):
        await super().setup(task_group)

        self.task_group.start_soon(self._check)

    async def list_bucket(
        self,
    ):
        async with self.list_lock:
            if time.perf_counter() - self.last_cache < 60:
                return
            async with self.session.resource(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            ) as resource:
                bucket = await resource.Bucket(self.bucket)
                self.cache_list_bucket = {}
                async for obj in bucket.objects.all():
                    cp = abc.CPath("/" + obj.key)
                    self.cache_list_bucket[str(cp)] = abc.FileInfo(
                        path=str(cp),
                        name=cp.name,
                        size=await obj.size,
                    )
                self.last_cache = time.perf_counter()

    async def list_files(
        self,
        path: str
    ) -> list[abc.FileInfo]:
        await self.list_bucket()
        # find by keys
        p = str(self.path / path)
        res = []
        for key in self.cache_list_bucket.keys():
            if str(abc.CPath(key).parents[-1]) == p:
                res.append(self.cache_list_bucket[key])
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
                await self.list_bucket()
                self.online = True
            except:
                self.online = False
            finally:
                self.emit_status()
                await anyio.sleep(300)
    
    async def get_response_file(self, hash: str) -> abc.ResponseFile:
        cpath = str(self.path / "download" / hash[:2] / hash)
        if cpath not in self.cache_list_bucket:
            return abc.ResponseFile(
                0
            )
        if self.custom_s3_host:
            return abc.ResponseFileRemote(
                f"{self.custom_s3_host}{cpath}",
                self.cache_list_bucket[cpath].size
            )
        if self.public_endpoint:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
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
                    self.cache_list_bucket[cpath].size
                )
        async with self.session.resource(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
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
            