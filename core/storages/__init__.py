import abc
import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
import hashlib
import inspect
import io
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import time
from typing import Any, Optional, TypeVar

import aiofiles
import aiohttp

from core import cache, config, logger
from core import utils
from core.utils import WrapperTQDM
import urllib.parse as urlparse

import aiowebdav.client as webdav3_client
import aiowebdav.exceptions as webdav3_exceptions


DOWNLOAD_DIR = "download"
MEASURE_DIR = "measure"
ALIST_TOKEN_DEAULT_EXPIRY = 86400 * 2

@dataclass
class File:
    name: str
    size: int
    mtime: float
    hash: str

    def __hash__(self):
        return self.hash.__hash__()
    
@dataclass
class MeasureFile:
    size: int

    def __hash__(self) -> int:
        return hash(self.size)


class FilePath(object):
    def __init__(self, path: str) -> None:
        self._path = FilePath._fix_path(path)

    @staticmethod
    def _fix_path(path: str):
        return path.replace("\\", "/").rstrip("/")
    
    @property
    def parents(self):
        result = []
        for i in range(1, len(self._path.split("/"))):
            result.append(FilePath("/".join(self._path.split("/")[:i])))
        return result
    
    @property
    def parent(self):
        return FilePath(self._path.rsplit("/", 1)[-2])
    
    @property
    def name(self):
        return self._path.rsplit("/")[-1]
    
    @property
    def path(self):
        return self._path
    
    def __str__(self):
        return self._path
    
    def __repr__(self):
        return f"FilePath({self._path})"
    
    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, FilePath):
            return self._path == __o._path
        return False
    
    def __hash__(self):
        return self._path.__hash__()
    
    def __truediv__(self, __o: Any) -> 'FilePath':
        if isinstance(__o, str):
            return FilePath(self._path + "/" + __o)
        elif isinstance(__o, FilePath):
            return FilePath(self._path + "/" + __o._path)
        else:
            raise TypeError(f"Unsupported type {type(__o)}")
        
    def __rtruediv__(self, __o: Any) -> 'FilePath':
        if isinstance(__o, str):
            return FilePath(__o + "/" + self._path)
        elif isinstance(__o, FilePath):
            return FilePath(__o._path + "/" + self._path)
        else:
            raise TypeError(f"Unsupported type {type(__o)}")


CollectionFile = MeasureFile | File
Range = lambda: range(0, 256)


class iStorage(metaclass=abc.ABCMeta):
    type: str = "_interface"
    def __init__(
        self, 
        path: str, 
        weight: int = 0, 
        list_concurrent: int = 32, 
        name: Optional[str] = None
    ):
        self.path = FilePath(path)
        self.weight = weight
        self.list_concurrent = list_concurrent
        self.current_weight = 0
        self._name = name
    
    @property
    @abc.abstractmethod
    def unique_id(self):
        raise NotImplementedError("unique_id not implemented")

    @property
    def name(self):
        if self._name is None:
            return self.unique_id
        else:
            return self._name

    def __repr__(self):
        return f"{self.type}({self.path})"

    @abc.abstractmethod
    async def list_files(self, pbar: WrapperTQDM) -> set[File]:
        raise NotImplementedError("list_files not implemented")
    
    @abc.abstractmethod
    async def write_file(self, file: CollectionFile, content: io.BytesIO):
        raise NotImplementedError("write_file not implemented")
    
    @abc.abstractmethod
    async def read_file(self, file: File) -> io.BytesIO:
        raise NotImplementedError("read_file not implemented")
    
    @abc.abstractmethod
    async def delete_file(self, file: CollectionFile):
        raise NotImplementedError("delete_file not implemented")
    
    @abc.abstractmethod
    async def exists(self, file: CollectionFile) -> bool:
        raise NotImplementedError("exists not implemented")
    
    @abc.abstractmethod
    async def get_size(self, file: CollectionFile) -> int:
        raise NotImplementedError("get_size not implemented")
    
    @abc.abstractmethod
    async def get_mtime(self, file: CollectionFile) -> float:
        raise NotImplementedError("get_mtime not implemented")
    
    def get_path(self, file: CollectionFile):
        if isinstance(file, MeasureFile):
            return self.path / MEASURE_DIR / str(file.size)
        else:
            return self.path / DOWNLOAD_DIR / file.hash[:2] / file.hash
    
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

class iNetworkStorage(iStorage):
    def __init__(
        self, 
        path: str, 
        username: str, 
        password: str, 
        endpoint: str, 
        weight: int = 0, 
        list_concurrent: int = 32, 
        name: Optional[str] = None,
        cache_timeout: float = 60,
    ):
        super().__init__(path, weight, list_concurrent, name)
        self.username = username
        self.password = password
        self.endpoint = endpoint.rstrip("/")
        self.cache = cache.TimeoutCache(cache_timeout)

    @property
    def unique_id(self):
        return hashlib.md5(f"{self.type},{self.path},{self.endpoint}".encode("utf-8")).hexdigest()
    
    def __repr__(self):
        return f"{self.__class__.__name__}(path={self.path}, endpoint={self.endpoint})"

@dataclass
class AlistResult:
    code: int
    message: str
    data: Any

@dataclass
class AlistToken:
    value: str
    expires: float

@dataclass
class AlistFileInfo:
    name: str
    size: int
    is_dir: bool
    modified: float
    created: float
    sign: str
    raw_url: str

class AlistError(Exception):
    def __init__(self, result: AlistResult):
        super().__init__(f"Status: {result.code}, Message: {result.message}")
        self.result = result

class AlistStorage(iNetworkStorage):
    type = "alist"

    def __init__(
        self, 
        path: str, 
        username: str, 
        password: str, 
        endpoint: str, 
        weight: int = 0, 
        list_concurrent: int = 32, 
        name: Optional[str] = None,
        cache_timeout: float = 60,
        retries: int = 3, 
        public_webdav_endpoint: str = ""
    ):
        super().__init__(path, username, password, endpoint, weight, list_concurrent, name, cache_timeout)
        self.retries = retries
        self.last_token: Optional[AlistToken] = None
        self.session = aiohttp.ClientSession(
            headers={
                "User-Agent": config.USER_AGENT
            }
        )
        if public_webdav_endpoint:
            urlobject = urlparse.urlparse(public_webdav_endpoint)
            self._public_webdav_endpoint = f"{urlobject.scheme}://{urlparse.quote(self.username)}:{urlparse.quote(self.password)}@{urlobject.netloc}{urlobject.path}"

    async def _get_token(self):
        if self.last_token is None or self.last_token.expires < time.monotonic():
            async with self.session.post(f"{self.endpoint}/api/auth/login", json={"username": self.username, "password": self.password}) as resp:
                r = AlistResult(
                    **(await resp.json())
                )
            try:
                if r.code == 200:
                    self.last_token = AlistToken(
                        value=r.data["token"],
                        expires=time.monotonic() + ALIST_TOKEN_DEAULT_EXPIRY - 3600
                    )
                else:
                    raise AlistError(r)
            except:
                logger.terror("storage.error.alist.fetch_token", status=r.code, message=r.message)
        if self.last_token is None:
            raise AlistError(AlistResult(500, "Failed to fetch token", None))
        return self.last_token.value
    
    async def __action_data(self, method: str, path: str, data: Any, headers: dict[str, Any] = {}, _authentication: bool = False, _retries: int = 0):
        key = hash((
            method,
            path,
            repr(headers),
            repr(data)
        ))
        res = self.cache.get(key)
        if res is not cache.EMPTY:
            return res
        async with self.session.request(
            method, f"{self.endpoint}{path}",
            data=data,
            headers={
                **headers,
                "Authorization": await self._get_token()
            }
        ) as resp:
            try:
                result = AlistResult(
                    **await resp.json()
                )
                if result.code == 401 and not _authentication:
                    self.last_token = None
                    return await self.__action_data(method, path, data, headers, True, _retries + 1)
                if result.code != 200:
                    if _retries < self.retries:
                        return await self.__action_data(method, path, data, headers, _authentication, _retries + 1)
                    logger.terror("storage.error.action_alist", method=method, url=resp.url, status=result.code, message=result.message)
                    logger.debug(data)
                    logger.debug(result)
                else:
                    self.cache.set(
                        key,
                        result,
                        60
                    )
                return result
            except:
                logger.terror("storage.error.alist", status=resp.status, message=await resp.text())
                raise
    
    async def list_files(self, pbar: WrapperTQDM) -> set[File]:
        async def get_files(root_id: int):
            root = self.path / DOWNLOAD_DIR / f"{root_id:02x}"
            try:
                async with sem:
                    async with self.session.post(
                        f"{self.endpoint}/api/fs/list",
                        headers={
                            "Authorization": await self._get_token()
                        },
                        data={
                            "path": str(root),
                        }
                    ) as resp:
                        result = AlistResult(
                            **await resp.json()
                        )
                        return ((result.data or {}).get("content", None) or [])
            except:
                logger.traceback()
            finally:
                pbar.update(1)
            return []

        sem = asyncio.Semaphore(self.list_concurrent)
        results = set()
        for result in await asyncio.gather(*(
            get_files(root_id)
            for root_id in Range()
        )):
            for file in result:
                results.add(File(
                    file["name"],
                    file["size"],
                    utils.parse_isotime_to_timestamp(file["modified"]),
                    file["name"]
                ))

        return results
    
    async def __info_file(self, file: CollectionFile) -> AlistFileInfo:
        r = await self.__action_data(
            "post",
            "/api/fs/get",
            {
                "path": str(self.get_path(file)),
                "password": ""
            },
        )
        name = file.hash if isinstance(file, File) else str(file.size)
        if r.code == 500:
            return AlistFileInfo(
                name,
                -1,
                False,
                0,
                0,
                "",
                ""
            )
        return AlistFileInfo(
            r.data["name"],
            r.data["size"],
            r.data["is_dir"],
            utils.parse_isotime_to_timestamp(r.data["modified"]),
            utils.parse_isotime_to_timestamp(r.data["created"]),
            r.data["sign"],
            r.data["raw_url"]
        )

    async def read_file(self, file: File) -> io.BytesIO:
        info = await self.__info_file(file)
        if info.size == -1:
            return io.BytesIO()
        async with self.session.get(
            info.raw_url
        ) as resp:
            return io.BytesIO(await resp.read())
        
    async def get_url(self, file: CollectionFile) -> str:
        if self._public_webdav_endpoint:
            return f"{self._public_webdav_endpoint}{str(self.get_path(file))}"
        info = await self.__info_file(file)
        return '' if info.size == -1 else info.raw_url
    
    async def write_file(self, file: MeasureFile | File, content: io.BytesIO):
        result = await self.__action_data(
            "put",
            "/api/fs/put",
            content.getvalue(),
            {
                "File-Path": urlparse.quote(str(self.get_path(file))),
            }
        )
        return result.code == 200
    
    async def close(self):
        await self.session.close()

    async def delete_file(self, file: MeasureFile | File):
        await self.__action_data(
            "post",
            "/api/fs/delete",
            {
                "path": str(self.get_path(file)),
                "password": ""
            }
        )

    async def exists(self, file: MeasureFile | File) -> bool:
        info = await self.__info_file(file)
        return info.size != -1
    
    async def get_mtime(self, file: MeasureFile | File) -> float:
        return (await self.__info_file(file)).modified
    
    async def get_size(self, file: MeasureFile | File) -> int:
        info = await self.__info_file(file)
        return max(0, info.size)
    
@dataclass
class WebDavFileInfo:
    created: float
    modified: float
    name: str
    size: int

@dataclass
class WebDavFile:
    hash: str
    size: int
    url: str = ""
    data: io.BytesIO = field(default_factory=io.BytesIO)
    headers: dict[str, Any] = field(default_factory=dict)

    def set_expires(self, value: float):
        self._expires = value + time.monotonic()

    @property
    def expired(self) -> bool:
        if hasattr(self, "_expires"):
            return self._expires < time.monotonic()
        return True
    
    def data_size(self) -> int:
        return len(self.data.getbuffer())

class WebDavStorage(iNetworkStorage):
    type = "webdav"
    def __init__(
        self, 
        path: str, 
        username: str, 
        password: str, 
        endpoint: str, 
        weight: int = 0, 
        list_concurrent: int = 32,
        name: Optional[str] = None, 
        cache_timeout: int = 60,
        public_endpoint: str = "", 
        retries: int = 3
    ):
        super().__init__(path, username, password, endpoint, weight, list_concurrent, name, cache_timeout)
        self.client = webdav3_client.Client({
            "webdav_hostname": endpoint,
            "webdav_login": username,
            "webdav_password": password,
            "User-Agent": config.USER_AGENT
        })
        self.public_endpoint = public_endpoint
        self.client_lock = asyncio.Lock()
        self.session = aiohttp.ClientSession(
            auth=aiohttp.BasicAuth(username, password),
            headers={
                "User-Agent": config.USER_AGENT
            }
        )
        urlobject = urlparse.urlparse(f"{self.public_endpoint or self.endpoint}")
        self.base_url = f"{urlobject.scheme}://{urlparse.quote(self.username)}:{urlparse.quote(self.password)}@{urlobject.hostname}:{urlobject.port}{urlobject.path}"
        self.retries = retries

    async def list_files(self, pbar: WrapperTQDM) -> set[File]:
        async def get_files(root_id: int) -> list[WebDavFileInfo]:
            root = self.path / DOWNLOAD_DIR / f"{root_id:02x}"
            retries = 0
            while retries < self.retries:
                try:
                    async with sem:
                        result = await self.client.list(
                            str(root),
                            True
                        )
                    return [WebDavFileInfo(
                        created=utils.parse_isotime_to_timestamp(r["created"]),
                        modified=utils.parse_gmttime_to_timestamp(r["modified"]),
                        name=r["name"],
                        size=int(r["size"])
                    ) for r in result if not r["isdir"]]
                except webdav3_exceptions.RemoteResourceNotFound:
                    retries += 1
                    ...
                except:
                    logger.traceback()
                    retries += 1
                finally:
                    pbar.update(1)
            return []

        sem = asyncio.Semaphore(self.list_concurrent)
        results = set()
        for result in await asyncio.gather(*(
            get_files(root_id)
            for root_id in Range()
        )):
            for file in result:
                results.add(File(
                    name=file.name,
                    hash=file.name,
                    size=file.size,
                    mtime=file.modified,
                ))

        return results
    
    async def _info_file(self, file: CollectionFile) -> WebDavFileInfo:
        key = hash(file)
        res = self.cache.get(key)
        if res is not cache.EMPTY:
            return res
        try:
            res = await self.client.info(str(self.get_path(file)))
        except:
            return WebDavFileInfo(
                created=0,
                modified=0,
                name=file.hash if isinstance(file, File) else str(file.size),
                size=-1
            )
        result = WebDavFileInfo(
            created=utils.parse_isotime_to_timestamp(res["created"]),
            modified=utils.parse_gmttime_to_timestamp(res["modified"]),
            name=res["name"],
            size=int(res["size"])
        )
        self.cache.set(key, result, 60)
        return result

    async def get_mtime(self, file: MeasureFile | File) -> float:
        return (await self._info_file(file)).modified
    
    async def get_size(self, file: MeasureFile | File) -> int:
        return (await self._info_file(file)).size
    
    async def exists(self, file: MeasureFile | File) -> bool:
        return (await self._info_file(file)).size != -1
    
    async def delete_file(self, file: MeasureFile | File):
        await self.client.unpublish(str(self.get_path(file)))
        return True
    
    async def read_file(self, file: File) -> io.BytesIO:
        data = io.BytesIO()
        if (await self._info_file(file)).size == -1:
            return data
        await self.client.download_from(data, str(self.get_path(file)))
        return data
    
    async def _mkdir(self, dir: str):
        async with self.client_lock:
            d = ""
            for x in dir.split("/"):
                d += x
                if d:
                    await self.client.mkdir(d)
                d += "/"
    
    async def get_file(self, file: CollectionFile) -> WebDavFile:
        # by old code
        f = WebDavFile(
            file.hash if isinstance(file, File) else str(file.size),
            0
        )

        # replace url to basic auth url

        url = f"{self.base_url}{self.get_path(file)}"
        f.url = url
        return f
    
    async def write_file(self, file: MeasureFile | File, content: io.BytesIO):
        path = self.get_path(file)
        await self._mkdir(str(path.parent))
        try:
            await self.client.upload_to(
                content,
                str(path),
            )
        except:
            logger.traceback()
            return False
        return True
    

@dataclass
class Parameter:
    name: str
    type: type
    default: Any = inspect._empty

def init_storage(config: Any) -> Optional[iStorage]:
    if not isinstance(config, dict) or "type" not in config or config["type"] not in abstract_storages:
        return None
    try:
        abstract_storage = abstract_storages[config["type"]]
        args = abstract_storage_args[abstract_storage]
        params = {}
        for arg in args:
            if arg.name in config:
                params[arg.name] = config[arg.name]
            elif arg.default != inspect._empty:
                params[arg.name] = arg.default
        print(params, config)
        return abstract_storage(**params)
    except:
        logger.traceback()
        return None

abstract_storages: dict[str, type[iStorage]] = {}
abstract_storage_args: defaultdict[type[iStorage], list[Parameter]] = defaultdict(list)

T = TypeVar("T")

def find_subclasses(base_class: type[T]) -> list[type[T]]:
    subclasses = []
    for name, obj in inspect.getmembers(inspect.getmodule(base_class)):
        if inspect.isclass(obj) and issubclass(obj, base_class) and obj!= base_class:
            subclasses.append(obj)
    return subclasses

async def init():
    for istorage in find_subclasses(iStorage):
        if istorage.type == iStorage.type:
            continue
        abstract_storages[istorage.type] = istorage
        arg = inspect.getfullargspec(istorage.__init__)
        args = arg.args[1:]
        # defaults 默认的长度和位置都是从后往前数的，
        # 填充一些空的在前面
        defaults = [
            inspect._empty for _ in range(len(args) - len(arg.defaults or []))
        ]
        defaults.extend(arg.defaults or [])
        for idx, arg_name in enumerate(args):
            if arg_name == "self":
                continue
            abstract_storage_args[istorage].append(
                Parameter(
                    name=arg_name,
                    type=arg.annotations.get(arg_name, Any),
                    default=defaults[idx]
                )
            )

    logger.debug("Storage init complete")
    logger.debug(f"Found {len(abstract_storages)} storage types: {', '.join(abstract_storages.keys())}")