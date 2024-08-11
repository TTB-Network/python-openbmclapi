from core.cluster import Cluster
from core.logger import logger
from core.i18n import locale
import humanize

async def init():
    cluster = Cluster()
    await cluster.token.fetchToken()
    await cluster.fetchFileList()
    await cluster.init()
    ready = await cluster.check()
    logger.tinfo('storage.info.check')
    if ready:
        logger.tsuccess('storage.success.check')
    else:
        raise Exception(locale.t('storage.error.check'))
    try:
        missing_filelist = [await storage.getMissingFiles(cluster.filelist) for storage in cluster.storages]
        missing_files_count = sum(len(filelist) for filelist in missing_filelist)
        missing_files_size = sum(sum(file.size for file in filelist) for filelist in missing_filelist)
        logger.tsuccess('storage.success.get_missing', count=humanize.intcomma(missing_files_count), size=humanize.naturalsize(missing_files_size))
    except Exception as e:
        logger.terror('storage.error.get_missing', e=e)