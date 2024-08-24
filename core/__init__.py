import asyncio
from core.cluster import Cluster
from core.config import Config
from core.logger import logger

cluster = Cluster()

async def main():
    try:
        await cluster.token.fetchToken()
        await cluster.getConfiguration()
        await cluster.fetchFileList()
        await cluster.init()
        await cluster.checkStorages()
        missing_filelist = await cluster.getMissingFiles()
        await cluster.syncFiles(missing_filelist, Config.get("advanced.retry"), Config.get("advanced.delay"))
        await cluster.connect()

        protocol = "http" if Config.get("cluster.byoc") else "https"
        if protocol == "https":
            await cluster.socket.requestCertificate()

        await cluster.setupRouter()
        await cluster.listen(protocol == "https", Config.get("cluster.port"))
        await cluster.enable()

        while True:
            await asyncio.sleep(3600)

    except asyncio.CancelledError:
        logger.tinfo('main.info.stopping')
        if cluster.enabled:
            await cluster.disable()
        if cluster.socket:
            await cluster.socket.socket.disconnect()
        if cluster.site:
            await cluster.site.stop()
        logger.tsuccess("main.success.stopped")

def init():
    loop = asyncio.get_event_loop()
    main_task = loop.create_task(main())
    try:
        loop.run_until_complete(main_task)
    except KeyboardInterrupt:
        main_task.cancel()
        loop.run_until_complete(asyncio.shield(main_task))
    finally:
        loop.close()