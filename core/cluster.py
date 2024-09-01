# TODO: 为每个集群创建一个类

from dataclasses import dataclass
import hashlib
import hmac
import time
from typing import Optional
import pyzstd as zstd
import aiohttp

from . import config
from . import scheduler


@dataclass
class Token:
    last: float
    token: str
    ttl: float

@dataclass
class File:
    path: str
    hash: str
    size: int
    mtime: int
    

class ClusterManagers:
    def __init__(self):
        self.clusters: list['Cluster'] = []
    
    async def get_filelist(self):
        ...

    async def _get_filelist(self, cluster: 'Cluster'):
        async with aiohttp.ClientSession(
            config.const.base_url,
            headers={
                "Authorization": f"Bearer {await cluster.get_token()}"
            }
        ) as session:
            async with session.get(
                f"/openbmclapi/files",
                params={
                    "clusterId": cluster.id
                }
            ) as resp:
                resp.raise_for_status()
                if resp.status == 204:
                    return []
                data = zstd.decompress(await resp.read())



class Cluster:
    def __init__(self, id: str, secret: str):
        self.id = id
        self.secret = secret
        self.token: Optional[Token] = None
        self.last_token: float = 0
        self.token_ttl: float = 0

    async def get_token(self):
        if self.token is None or time.time() - self.last_token > self.token_ttl - 300:
            await self.fetch_token()

        if self.token is None or self.token.last + self.token.ttl < time.time():
            raise RuntimeError('token expired')
        
        return self.token.token

    async def fetch_token(self):
        async with aiohttp.ClientSession(
            config.const.base_url
        ) as session:
            async with session.get(
                f"/openbmclapi-agent/challenge",
                params={
                    "clusterId": self.id
                }
            ) as resp:
                challenge = (await resp.json())['challenge']
                signature = hmac.new(
                    self.secret.encode("utf-8"), digestmod=hashlib.sha256
                )
                signature.update(challenge.encode())
                signature = signature.hexdigest()
            async with session.post(
                "/openbmclapi-agent/token",
                data = {
                    "clusterId": self.id,
                    "challenge": challenge,
                    "signature": signature,
                }
            ) as resp:
                resp.raise_for_status()
                json = await resp.json()
                self.token = Token(time.time(), json['token'], json['ttl'] / 1000.0)
                self.fetch_time = time.monotonic()
                if self.scheduler is not None:
                    scheduler.cancel(self.scheduler)
                self.scheduler = scheduler.run_later(self.get_token, delay=self.token.ttl - 300)
