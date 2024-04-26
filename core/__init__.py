import asyncio
import sys
import time
from .env import env as env
import atexit
from .logger import logger
from .scheduler import init as scheduler_init
from .scheduler import exit as scheduler_exit
from .utils import WaitLock

env['MONOTONIC'] = time.monotonic()
env['STARTUP'] = time.time()

wait_exit: WaitLock = WaitLock()

def init():
    wait_exit.acquire()
    logger.tinfo("core.info.loading")
    version = sys.version_info
    logger.tinfo("core.info.python_version", 
                 v=f"{str(version.major)}.{str(version.minor)}.{str(version.micro)}")
    atexit.register(exit)
    try:
        asyncio.run(async_init())
    except KeyboardInterrupt:
        if wait_exit.locked:
            wait_exit.release()

async def async_init():
    # first init
    await scheduler_init()
    # load modules
    from .network import init as network_init
    from .network import close as network_exit
    from .cluster import init as cluster_init
    from .cluster import exit as cluster_exit
    from .stats import init as stats_init
    scheduler.delay(network_init)
    stats_init()
    await cluster_init()

    await wait_exit.wait()
    env['EXIT'] = True
    network_exit()
    await cluster_exit()
    scheduler_exit()


def exit():
    if wait_exit.locked:
        wait_exit.release()
    logger.tsuccess("core.success.exit")
