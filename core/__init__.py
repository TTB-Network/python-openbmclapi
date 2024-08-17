from core.cluster import Cluster
from core.config import Config

async def init():
    cluster = Cluster()
    await cluster.token.fetchToken()
    await cluster.getConfiguration()
    await cluster.fetchFileList()
    await cluster.init()
    await cluster.checkStorages()
    missing_filelist = await cluster.getMissingFiles()
    delay = Config.get('advanced.delay')
    retry = Config.get('advanced.retry')
    await cluster.syncFiles(missing_filelist, retry, delay)