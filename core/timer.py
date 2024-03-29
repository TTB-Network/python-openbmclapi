import asyncio
import inspect
import os
import time
import traceback
from core.logger import logger


class Task:
    def __init__(
        self,
        target,
        args,
        loop: bool = False,
        delay: float = 0,
        interval: float = 0,
        back=None,
        error=None,
    ) -> None:
        self.target = target
        self.args = args
        self.loop = loop
        self.delay = delay
        self.interval = interval
        self.last = 0.0
        self.create_at = time.time()
        self.blocked = False
        self.back = back
        self.error = error
        self.called = False
        self.cur = None

    async def call(self):
        if self.blocked or not int(os.environ["ASYNCIO_STARTUP"]):
            return
        try:
            if inspect.iscoroutinefunction(self.target):
                self.cur = await asyncio.create_task(self.target(*self.args))
            else:
                self.cur = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.target(*self.args)
                )
            if not self.loop:
                self.called = True
            await self.callback()
        except asyncio.CancelledError:
            return
        except:
            await self.callback_error()

    async def callback(self):
        if not self.back or not int(os.environ["ASYNCIO_STARTUP"]):
            return
        try:
            if inspect.iscoroutinefunction(self.back):
                self.cur = await asyncio.create_task(self.back())
            else:
                self.cur = await asyncio.get_event_loop().run_in_executor(
                    None, self.back
                )
        except:
            await self.callback_error()

    def block(self):
        if self.cur:
            self.cur.cancel()
        self.blocked = True

    async def callback_error(self):
        if not self.error or not int(os.environ["ASYNCIO_STARTUP"]):
            logger.debug(traceback.format_exc())
            return
        try:
            if inspect.iscoroutinefunction(self.error):
                self.cur = await asyncio.create_task(self.error())
            else:
                self.cur = await asyncio.get_event_loop().run_in_executor(
                    None, self.error
                )
        except:
            logger.debug(traceback.format_exc())


class TimerManager:
    def delay(self, target, args=(), delay: float = 0, callback=None, error=None):
        task = Task(target=target, args=args, delay=delay, back=callback, error=error)
        asyncio.get_event_loop().call_later(
            task.delay,
            lambda: asyncio.run_coroutine_threadsafe(
                task.call(), asyncio.get_event_loop()
            ),
        )
        return task

    def repeat(
        self,
        target,
        args=(),
        delay: float = 0,
        interval: float = 0,
        callback=None,
        error=None,
    ):
        task = Task(
            target=target,
            args=args,
            delay=delay,
            loop=True,
            interval=interval,
            back=callback,
            error=error,
        )
        asyncio.get_event_loop().call_later(task.delay, lambda: self._repeat(task))
        return task

    def _repeat(self, task: Task):
        asyncio.get_event_loop().call_later(
            0,
            lambda: asyncio.run_coroutine_threadsafe(
                task.call(), asyncio.get_event_loop()
            ),
        )
        asyncio.get_event_loop().call_later(task.interval, lambda: self._repeat(task))


Timer: TimerManager = TimerManager()
