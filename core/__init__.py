import asyncio
from core.cluster import Cluster
from core.config import Config
from core.logger import logger
from core.scheduler import scheduler, IntervalTrigger

cluster = Cluster()


async def main():
    try:
        await cluster.token.fetchToken()
        await cluster.getConfiguration()
        await cluster.fetchFileList()
        await cluster.init()
        await cluster.checkStorages()

        async def syncFiles():
            missing_filelist = await cluster.getMissingFiles()
            await cluster.syncFiles(
                missing_filelist,
                Config.get("advanced.retry"),
                Config.get("advanced.delay"),
            )

        await syncFiles()
        scheduler.add_job(
            syncFiles,
            trigger=IntervalTrigger(minutes=Config.get("advanced.sync_interval")),
        )
        await cluster.connect()
        protocol = "http" if Config.get("cluster.byoc") else "https"
        if protocol == "https":
            await cluster.socket.requestCertificate()
        await cluster.setupRouter()
        await cluster.listen(protocol == "https", Config.get("cluster.port"))
        await cluster.enable()
        if not cluster.enabled:
            raise asyncio.CancelledError
        scheduler.add_job(
            cluster.keepAlive,
            IntervalTrigger(seconds=Config.get("advanced.keep_alive")),
        )
        scheduler.start()
        logger.tsuccess("main.success.scheduler")
        while True:
            await asyncio.sleep(3600)

    except asyncio.CancelledError:
        logger.tinfo("main.info.stopping")
        if cluster.enabled:
            await cluster.disable()
        if cluster.socket:
            await cluster.socket.socket.disconnect()
        if cluster.http_site:
            await cluster.http_site.stop()
        if cluster.https_site:
            await cluster.https_site.stop()
        if scheduler.state == 1:
            scheduler.shutdown()
        logger.tsuccess("main.success.stopped")


def init():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
