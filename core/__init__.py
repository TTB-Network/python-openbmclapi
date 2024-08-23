from core.cluster import Cluster
from core.config import Config
import asyncio


async def init():
    cluster = Cluster()
    await cluster.token.fetchToken()
    await cluster.getConfiguration()
    await cluster.fetchFileList()
    await cluster.init()
    await cluster.checkStorages()
    missing_filelist = await cluster.getMissingFiles()
    delay = Config.get("advanced.delay")
    retry = Config.get("advanced.retry")
    await cluster.syncFiles(missing_filelist, retry, delay)
    await cluster.connect()
    protocol = "http" if Config.get("cluster.byoc") else "https"
    if protocol == "https":
        await cluster.socket.requestCertificate()
    await cluster.setupRouter(protocol == "https", port=Config.get("cluster.port"))
    await cluster.enable()
    try:
        while True:
            await asyncio.sleep(1000)
    except KeyboardInterrupt:
        raise KeyboardInterrupt
