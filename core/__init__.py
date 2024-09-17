import asyncio
import time
from .logger import logger
from . import utils
import atexit
from . import cluster
from . import scheduler
from . import web
from . import dashboard
from . import database

_WAITLOCK = utils.CountLock()
_START_RUNTIME = time.monotonic()

async def main():
    start = time.monotonic_ns()
    await scheduler.init()
    await database.init()
    await web.init()
    await dashboard.init()
    await cluster.init()
    _WAITLOCK.acquire()
    end = time.monotonic_ns()
    logger.tsuccess("main.success.start_service_done", time=f"{((end-start) / 1e9):.2f}")
    try:
        await _WAITLOCK.wait()
    except:
        logger.tdebug("main.debug.service_unfinish")
    finally:
        await cluster.unload()
        await web.unload()
        await database.unload()
        await scheduler.unload()

def init():
    atexit.register(main_exit)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.debug("KeyboardInterrupt")
    finally:
        atexit.unregister(main_exit)
    logger.tsuccess("main.success.service_exit")

def main_exit():
    _WAITLOCK.release()