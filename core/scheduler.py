import asyncio
import time
from typing import Callable, Optional
from apscheduler.schedulers.background import (
    BackgroundScheduler as SyncBackground
)
from apscheduler.schedulers.asyncio import (
    AsyncIOScheduler as AsyncBackground
)
from apscheduler.job import Job
from . import logger
from weakref import WeakValueDictionary

from . import units

background = SyncBackground()
async_background: AsyncBackground
tasks: WeakValueDictionary[int, Job] = WeakValueDictionary()
_async_id: int = 0
_sync_id: int = 0
MAX_INSTANCES = 9999


async def init():
    global async_background
    async_background = AsyncBackground(
        event_loop=asyncio.get_event_loop()
    )

    background.start()
    async_background.start()

    logger.success('Background scheduler initialized')


async def unload():
    global async_background
    background.shutdown()
    async_background.shutdown()
    logger.success('Background scheduler unloaded')


def wrapper(func, args, kwargs):
    def sync_wrapper():
        return func(*args, **kwargs)

    async def async_wrapper():
        return await func(*args, **kwargs)
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def run_later(func: Callable, delay: float, args = (), kwargs = {}) -> int:
    global _sync_id, _async_id
    if asyncio.iscoroutinefunction(func):
        cur_id = -(_async_id := _async_id + 1)
        tasks[cur_id] = async_background.add_job(
            wrapper(func, args, kwargs), 'date', run_date=units.format_datetime_from_timestamp(time.time() + delay), max_instances=MAX_INSTANCES
        )
    else:
        cur_id = (_sync_id := _sync_id + 1)
        tasks[cur_id] = background.add_job(
            wrapper(func, args, kwargs), 'date', run_date=units.format_datetime_from_timestamp(time.time() + delay), max_instances=MAX_INSTANCES
        )
    return cur_id

def run_repeat_later(func: Callable, delay: float, interval: float, args = (), kwargs = {}) -> int:
    global _sync_id, _async_id
    delay = max(delay, 1)
    if asyncio.iscoroutinefunction(func):
        cur_id = -(_async_id := _async_id + 1)
        tasks[cur_id] = async_background.add_job(
            wrapper(func, args, kwargs), 'interval', seconds=interval, start_date=units.format_datetime_from_timestamp(time.time() + delay), max_instances=MAX_INSTANCES
        )
    else:
        cur_id = (_sync_id := _sync_id + 1)
        tasks[cur_id] = background.add_job(
            wrapper(func, args, kwargs), 'interval', seconds=interval, start_date=units.format_datetime_from_timestamp(time.time() + delay), max_instances=MAX_INSTANCES
        )
    return cur_id

def run_repeat(func: Callable, interval: float, args = (), kwargs = {}) -> int:
    return run_repeat_later(func, 0, interval, args, kwargs)

def cancel(task_id: Optional[int] = None):
    if task_id is None:
        return
    if task_id in tasks:
        try:
            tasks.pop(task_id).remove()
        except:
            logger.debug(f'Task {task_id} was cancelled')
            return
        logger.debug(f'Task {task_id} canceled')
    
