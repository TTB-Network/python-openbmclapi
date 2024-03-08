import asyncio
import base64
import os
import web
import hashlib
import hmac
import io
from pathlib import Path
import time
from typing import Any, Dict, Optional
import aiofiles
import aiohttp
import socketio
import globals
from utils import BMCLAPIFile, Task, Timer, calc_bytes, calc_more_bytes, error, get_file_hash, get_hash, info, traceback, updateDict
import pyzstd as zstd
from avro import schema, io as avro_io  
from stats import counter, Counters
import main
import config

prefixURL = 'https://openbmclapi.bangbang93.com/'
wsPrefixURL = 'wss://openbmclapi.bangbang93.com/'
headers = {
    "User-Agent": "openbmclapi-cluster/1.9.7"
}
class TokenManager:
    def __init__(self) -> None:
        self.token = None
    async def fetchToken(self):
        async with aiohttp.ClientSession(headers=headers) as session:  
            try:  
                async with session.get(prefixURL + "openbmclapi-agent/challenge", params={"clusterId": config.CLUSTER_ID}) as req:  
                    req.raise_for_status()  
                    challenge: str = (await req.json())['challenge']  
                      
                signature = hmac.new(config.CLUSTER_SECRET.encode("utf-8"), digestmod=hashlib.sha256)  
                signature.update(challenge.encode())  
                signature = signature.hexdigest()  
                  
                data = {  
                    "clusterId": config.CLUSTER_ID,  
                    "challenge": challenge,  
                    "signature": signature  
                }  
                  
                async with session.post(prefixURL + "openbmclapi-agent/token", json=data) as req:  
                    req.raise_for_status()  
                    content: Dict[str, Any] = await req.json()  
                    self.token = content['token']  
                    Timer.delay(self.fetchToken, delay=float(content['ttl']) / 1000.0 - 600)
              
            except aiohttp.ClientError as e:  
                error(f"Error fetching token: {e}")  
    async def getToken(self) -> str:  
        if not self.token:  
            await self.fetchToken()
        return self.token or ''

class FileStorage:
    def __init__(self, dir) -> None:
        self.dir = Path(dir)
        self.dir.mkdir(exist_ok=True, parents=True)
    async def missing_file(self, bmcl_files: list[BMCLAPIFile]):
        files = []
        task = []
        for n in bmcl_files:
            file = Path(str(self.dir) + "/" + n.hash[:2] + "/" + n.hash)
            if not file.exists():
                files.append(n)
                continue
            await asyncio.sleep(0.001)
            task.append(n)
        asyncio.create_task(self.hash_file(files, task))
        return files
    async def hash_file(self, files: list[BMCLAPIFile], file: list[BMCLAPIFile]):
        for n in file:
            if await get_file_hash(n.hash, Path(str(self.dir) + "/" + n.hash[:2] + "/" + n.hash)):
                continue
            files.append(n)
            await asyncio.sleep(0.001)

class FileDownloader:
    def __init__(self, authorization: str, bmcl_files: list[BMCLAPIFile], storage: FileStorage) -> None:
        self.bmcl_files = bmcl_files
        self.storage = storage
        self.success: int = 0
        self.queue: asyncio.Queue[BMCLAPIFile] = asyncio.Queue()
        self.authorization = authorization
        self.success_file = 0
    async def downloadFile(self):
        async with aiohttp.ClientSession(prefixURL, headers=updateDict(
            headers,
            {"Authorization": f"Bearer {self.authorization}"}
        )) as session:
            while not self.queue.empty():
                file = await self.queue.get()
                try:
                    h = hashlib.sha1()
                    async with session.get(file.path, timeout=5) as resp:
                        filepath = Path(str(self.storage.dir) + "/" + file.hash[:2] + "/" + file.hash)
                        filepath.parent.mkdir(exist_ok=True, parents=True)
                        async with aiofiles.open(filepath, "wb") as w:
                            while data := await resp.content.read(globals.BUFFER):
                                if not data:
                                    break
                                await w.write(data)
                                h.update(data)
                    if file.hash != h.hexdigest():
                        raise EOFError
                    self.success += file.size
                    self.success_file += 1
                except (EOFError, aiohttp.ClientConnectionError, aiohttp.ServerDisconnectedError, TimeoutError):
                    await self.queue.put(file)
                except:
                    traceback()
                    await self.queue.put(file)
                await asyncio.sleep(0.5)
    async def runTask(self):
        info(f"Checking missing files...")

        files = await self.storage.missing_file(self.bmcl_files)
        if not files:
            info(f"No missing files.")
            return
        total = sum((file.size for file in files))
        total_files = len(files)
        b = calc_bytes(total)
        info(f"Missing files! Total: {total_files}, {b[0]} {b[1]}iB")
        start = time.time()
        for file in files:
            await self.queue.put(file)
        [Timer.delay(self.downloadFile) for _ in range(config.MAX_DOWNLOAD)]
        while not self.queue.empty() or self.success != total_files:
            b = calc_more_bytes(self.success, total)
            info(f"Downloading files... {total_files - self.success_file} / {total_files}, {b[0][0]}{b[1]}iB / {b[0][1]}{b[1]}iB")
            await asyncio.sleep(1)
        info(f"Downloaded all files! Time: {time.time() - start:0.2f}s")

class Cluster:
    async def __call__(self) -> 'Cluster':
        self._port = config.publicPort
        self.publicPort = config.publicPort
        self.ua = config.USER_AGENT + "/" + version + " " + globals.PY_USER_AGENT
        self.authorization = await token.getToken()
        self.sio = socketio.AsyncClient()
        self.aio = aiohttp.ClientSession(
            base_url=prefixURL,
            headers=updateDict(headers, {
                "Authorization": f"Bearer {self.authorization}"
            })
        )
        info("Got cluster token")
        self.storage = FileStorage("./bmclapi")
        self.keepalive: Optional[Task] = None
        self.syncing = False
        return self
    async def getFileList(self):
        async with aiohttp.ClientSession(
            base_url=prefixURL,
            headers=updateDict(headers, {
                "Authorization": f"Bearer {self.authorization}"
            })
        ) as session:
            async with session.get('/openbmclapi/files', data={
                "responseType": "buffer",
                "cache": ""
            }) as resp:
                parser = avro_io.DatumReader(schema.parse(
'''  
{  
  "type": "array",  
  "items": {  
    "type": "record",  
    "name": "FileList",  
    "fields": [  
      {"name": "path", "type": "string"},  
      {"name": "hash", "type": "string"},  
      {"name": "size", "type": "long"}  
    ]  
  }  
}  
'''  ))
                decoder = avro_io.BinaryDecoder(io.BytesIO(zstd.decompress(await resp.read())))  
                return [BMCLAPIFile(**file) for file in parser.read(decoder)]

    async def connect(self):
        info("Connecting...")
        await self.sio.connect(prefixURL, 
            transports=['websocket'],
            auth={"token": self.authorization},
        )
        await self.enable()
    async def enable(self):
        if not self.sio.connected: 
            return
        await self.emit("enable", {
            "host": config.publicHost,
            "port": self.publicPort or self._port,
            "version": version,
            "byoc": config.ssl,
            "noFastEnable": False
        })
        if not (Path("./config/cert.pem").exists() and Path("./config/key.pem").exists()):
            await self.requestCert()
        self.cur_counter = Counters()
        info("Connected")
    async def message(self, type, data):
        if type == "request-cert":
            cert = data[1]
            info("Requested Cert!")
            cert_file = Path("./config/cert.pem")
            key_file = Path("./config/key.pem")
            for file in (cert_file, key_file):
                file.parent.mkdir(exist_ok=True, parents=True)
            with open(cert_file, "w") as w:
                w.write(cert['cert'])
            with open(key_file, "w") as w:
                w.write(cert['key'])
            main.load_cert()
            info(f"Loaded cert")
            for port in main.get_ports():
                main.ports[port].close()
                await main.start_server(port)
            info(f"Restart {', '.join((str(i) for i in main.port_))}")
        elif type == "enable":
            if self.keepalive:
                self.keepalive.block()
            self.keepalive = Timer.delay(self.keepaliveTimer, (), 5)
            if len(data) == 2 and data[1] == True:
                info("Checked! Can service")
                return
            error(data[0]['message'])
            Timer.delay(self.enable)
        elif type == "keep-alive":
            counter.hit -= self.cur_counter.hit
            counter.bytes -= self.cur_counter.bytes
            self.keepalive = Timer.delay(self.keepaliveTimer, (), 5)
    async def emit(self, channel, data = None):
        await self.sio.emit(channel, data, callback=lambda x: asyncio.run_coroutine_threadsafe(self.message(channel, x), asyncio.get_event_loop()))
    async def keepaliveTimer(self):
        self.cur_counter.hit = counter.hit
        self.cur_counter.bytes = counter.bytes
        await self.emit("keep-alive", {
            "time": time.time(),
            "hits": self.cur_counter.hit,
            "bytes": self.cur_counter.bytes
        })
    async def requestCert(self):
        await self.emit("request-cert")
    async def disable(self):
        await self.emit("disable")

    async def syncFile(self):
        info("Reuqesting files...")

        files = await self.getFileList()
        b = calc_bytes(sum((file.size for file in files)))

        info(f"Reuqested files! Total: {len(files)}, {b[0]} {b[1]}iB")
        self.syncing = True
        file = FileDownloader(self.authorization, files, self.storage)
        Timer.delay(file.runTask, callback=lambda: self.set_sync(False))
    def set_sync(self, sync):
        self.syncing = sync
    async def serve(self):
        Timer.repeat(self.syncFile, (), 0, 600)
        await self.connect()
        

class FileCache:
    def __init__(self, file: Path) -> None:
        self.buf = io.BytesIO()
        self.size = 0
        self.last_file = 0
        self.last = 0
        self.file = file
        self.access = 0
    async def __call__(self) -> io.BytesIO:
        self.access = time.time()
        if self.last < time.time():
            stat = self.file.stat()
            if self.size == stat.st_size and self.last_file == stat.st_mtime:
                self.last = time.time() + 600
                return self.buf
            self.buf.seek(0, os.SEEK_SET)
            async with aiofiles.open(self.file, "rb") as r:
                while (data := await r.read(min(globals.BUFFER, stat.st_size - self.buf.tell()))) and self.buf.tell() < stat.st_size:
                    self.buf.write(data)
                self.last = time.time() + 600
                self.size = stat.st_size
                self.last_file = stat.st_mtime
            self.buf.seek(0, os.SEEK_SET)
        return self.buf

token = TokenManager()
version = "1.9.7"
app = web.app
cache: dict[str, FileCache] = {}
cluster = None
async def init():
    global cluster
    if not cluster:
        cluster = await Cluster()()
        await (await Cluster()()).serve()

def check_sign(hash: str, secret: str, s: str, e: str):
    h = hmac.new(secret.encode("utf-8"), hash.encode("utf-8"), hashlib.sha1)
    h.update(e.encode("utf-8"))
    return base64.b64encode(h.digest()) == s and time.time() < int(e, 36)

@app.get("/measure/{size}")
async def _(request: web.Request, size: int, s: str, e: str):
    if not config.SKIP_SIGN:
        check_sign(request.protocol + "://" + request.host + request.path, config.CLUSTER_SECRET, s, e)
    async def iter(size):
        for _ in range(size):
            yield b'\x00' * 1024 * 1024
    return web.Response(iter(size))

@app.get("/download/{hash}")
async def _(request: web.Request, hash: str, s: str, e: str):
    if not config.SKIP_SIGN:
        check_sign(request.protocol + "://" + request.host + request.path, config.CLUSTER_SECRET, s, e)
    if not cluster:
        return web.Response(status_code=427)
    file = Path(str(cluster.storage.dir) + "/" + hash[:2] + "/" + hash)
    if hash not in cache:
        cache[hash] = FileCache(file)
    data = await cache[hash]()
    counter.bytes += len(data.getbuffer())
    counter.hit += 1
    return data.getbuffer()

async def clearCache():
    global cache
    data = cache.copy()
    for k, v in data.items():
        if v.access + 60 < time.time():
            cache.pop(k)


Timer.repeat(clearCache, (), 5, 10)
