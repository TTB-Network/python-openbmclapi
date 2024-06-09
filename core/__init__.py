import asyncio
import sys
import time
from .env import env as env
import atexit
from .logger import logger, socketio_logger
from .scheduler import init as scheduler_init
from .scheduler import exit as scheduler_exit
from .utils import WaitLock

env["MONOTONIC"] = time.monotonic()
env["STARTUP"] = time.time()

wait_exit: WaitLock = WaitLock()


def init():
    wait_exit.acquire()
    logger.tinfo("core.info.loading")
    version = sys.version_info
    logger.tinfo(
        "core.info.python_version", v=f"{version.major}.{version.minor}.{version.micro}"
    )
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
    from .network import exit as network_exit
    from .database import init as database_init
    from .cluster import init as cluster_init
    from .cluster import exit as cluster_exit
    from .statistics import init as stats_init
    from .statistics import exit as stats_exit
    from .update import init as update_init
    from .system import init as system_init
    import plugins 

    database_init()
    update_init()
    scheduler.delay(network_init)
    stats_init()
    await cluster_init()

    system_init()
    plugins.load_plugins()
    for plugin in plugins.get_plugins():
        await plugin.init()
        await plugin.enable()

    await wait_exit.wait()
    env["EXIT"] = True
    await cluster_exit()
    for plugin in plugins.get_enable_plugins():
        await plugin.disable()
    network_exit()
    stats_exit()
    scheduler_exit()


def exit():
    if wait_exit.locked:
        wait_exit.release()
    logger.tsuccess("core.success.exit")
