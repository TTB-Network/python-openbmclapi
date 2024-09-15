import asyncio
from core.cluster import Cluster
from core.config import Config
from core.logger import logger
from core.scheduler import scheduler, IntervalTrigger
from core import orm
import os

cluster = Cluster()


async def main():
    try:
        await cluster.token.fetchToken()
        await cluster.getConfiguration()
        await cluster.init()
        await cluster.checkStorages()
        logger.tinfo("orm.info.creating")
        try:
            os.makedirs("./database", exist_ok=True)
            orm.create()
            logger.tsuccess("orm.success.created")
        except Exception as e:
            logger.terror("orm.error.failed", e=e)

        async def syncFiles():
            if cluster.scheduler:
                cluster.scheduler.pause()
            if cluster.enabled and cluster.socket:
                await cluster.disable()
            await cluster.fetchFileList()
            missing_filelist = await cluster.getMissingFiles()
            await cluster.syncFiles(
                missing_filelist,
                Config.get("advanced.retry"),
                Config.get("advanced.delay"),
            )
            if not cluster.enabled and cluster.socket:
                await cluster.enable()
            if cluster.scheduler:
                cluster.scheduler.resume()

        await syncFiles()
        # scheduler.add_job(
        #     syncFiles,
        #     trigger=IntervalTrigger(minutes=Config.get("advanced.sync_interval")),
        #     max_instances=50,
        # )
        await cluster.connect()
        protocol = "http" if Config.get("cluster.byoc") else "https"
        if protocol == "https":
            await cluster.requestCertificate()
        await cluster.setupRouter()
        await cluster.listen(protocol == "https", Config.get("cluster.port"))
        await cluster.enable()
        if not cluster.enabled:
            raise asyncio.CancelledError
        scheduler.start()
        await asyncio.sleep(10)
        await cluster.keepAlive()
        logger.tsuccess("main.success.scheduler")
        while True:
            await asyncio.sleep(3600)

    except asyncio.CancelledError:
        logger.tinfo("main.info.stopping")
        if cluster.enabled:
            await cluster.disable()
        if cluster.socket:
            await cluster.socket.disconnect()
        if cluster.site:
            await cluster.site.stop()
        if scheduler.state == 1:
            scheduler.shutdown()
        logger.tsuccess("main.success.stopped")


def init():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
