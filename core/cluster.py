from core.config import Config
from core.logger import logger
from core.scheduler import *
from core.exceptions import ClusterIdNotSet, ClusterSecretNotSet
from core.storages import getStorages
from core.utils import FileInfo, FileList
import toml
import zstandard as zstd
import aiohttp
import asyncio
import hmac
import hashlib
import humanize
import io

API_VERSION = Config.get('advanced.api_version')
VERSION = toml.loads(open('pyproject.toml', 'r').read())['tool']['poetry']['version']

class Token:
    def __init__(self) -> None:
        self.user_agent = f'openbmclapi-cluster/{API_VERSION} python-openbmclapi/{VERSION}'
        self.base_url = Config.get('cluster.base_url')
        self.token = None
        self.id = Config.get('cluster.id')
        self.secret = Config.get('cluster.secret')
        self.ttl = 0 # hours
        self.scheduler = None
        if not self.id or not self.secret:
            raise ClusterIdNotSet if not self.id else ClusterSecretNotSet
    
    async def fetchToken(self):
        logger.tinfo('token.info.fetching')
        async with aiohttp.ClientSession(self.base_url, headers={"User-Agent": self.user_agent}) as session:
            async with session.get('/openbmclapi-agent/challenge', params={"clusterId": self.id}) as response:
                response.raise_for_status()
                challenge = (await response.json())['challenge']
            signature = hmac.new(self.secret.encode(), challenge.encode(), digestmod=hashlib.sha256)
            async with session.post('/openbmclapi-agent/token', data={"clusterId": self.id, "challenge": challenge, "signature": signature.hexdigest()}) as response:
                response.raise_for_status()
                res = await response.json()
                self.token = res['token']
                self.ttl = res['ttl'] / 3600000
                logger.tsuccess('token.success.fetched', ttl=int(self.ttl))
                if self.scheduler == None:
                    self.scheduler = Scheduler.add_job(self.fetchToken,IntervalTrigger(hours=self.ttl))

class Cluster:
    def __init__(self) -> None:
        self.user_agent = f'openbmclapi-cluster/{API_VERSION} python-openbmclapi/{VERSION}'
        self.base_url = Config.get('cluster.base_url')
        self.last_modified = 1000
        self.id = Config.get('cluster.id')
        self.secret = Config.get('cluster.secret')
        self.token = Token()
        self.filelist = FileList(files=[])
        self.storages = getStorages()

    async def fetchFileList(self) -> None:
        logger.tinfo('cluster.filelist.info.fetching')
        async with aiohttp.ClientSession(self.base_url, headers={
            'User-Agent': self.user_agent,
            'Authorization': f'Bearer {self.token.token}',
        }) as session:
            async with session.get('/openbmclapi/files', params={"lastModified": self.last_modified}) as response:
                response.raise_for_status()
                logger.tsuccess('cluster.filelist.success.fetched')
                decompressor = zstd.ZstdDecompressor().stream_reader(io.BytesIO(await response.read()))
                decompressed_data = io.BytesIO(decompressor.read())
                for _ in range(self.read_long(decompressed_data)):
                    self.filelist.files.append(FileInfo(
                        self.read_string(decompressed_data),
                        self.read_string(decompressed_data),
                        self.read_long(decompressed_data),
                        self.read_long(decompressed_data)
                    ))
                size = sum(file.size for file in self.filelist.files)
                logger.tsuccess('cluster.filelist.success.parsed', count=humanize.intcomma(len(self.filelist.files)), size=humanize.naturalsize(size))

    async def init(self) -> None:
        await asyncio.gather(*(storage.init() for storage in self.storages))
    
    async def check(self) -> bool:
        results = await asyncio.gather(*(storage.check() for storage in self.storages))
        return all(results)

    def read_long(self, stream: io.BytesIO):
        b = ord(stream.read(1))
        n = b & 0x7F
        shift = 7
        while (b & 0x80) != 0:
            b = ord(stream.read(1))
            n |= (b & 0x7F) << shift
            shift += 7
        return (n >> 1) ^ -(n & 1)

    def read_string(self, stream: io.BytesIO):
        return stream.read(self.read_long(stream)).decode("utf-8")
