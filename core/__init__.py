from core.cluster import Cluster
from core.config import Config
import asyncio
import signal

cluster = Cluster()


async def main():
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
    await cluster.setupRouter()
    await cluster.listen(protocol == "https", Config.get("cluster.port"))
    await cluster.enable()
    while True:
        await asyncio.sleep(3600)


def init():
    asyncio.run(main())
