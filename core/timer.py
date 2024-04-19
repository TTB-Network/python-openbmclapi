import asyncio
import inspect
import os
import time
import traceback
from typing import Any, Callable, Optional
from core.logger import logger as log
from core.const import *
from core.i18n import locale

logger = log.depth(2)


class Task:
    def __init__(
        self,
        handler: Callable,
        args: Optional[tuple] = (),
        kwargs: Optional[dict[str, Any]] = {},
        delay: float = 1,
        interval: Optional[float] = None,
    ) -> None:
        self._handler = handler
        self._args = args
        self._kwargs = kwargs
        self._delay = delay
        self._interval = interval
        self._create_at = time.monotonic()
        self._cur_task = None
        self._called = False
        self._blocked = False
        self._task = None
        self._frame = inspect.stack()[2]
        self._frame_name = f"{parse_filename(self._frame.filename)}:{self._frame.function}:{self._frame.lineno}"

    def is_called(self):
        return self._called

    def get_create_at(self):
        return self._cur_task

    def is_blocked(self):
        return self._blocked

    def _get_function_name(self):
        return self._frame_name

    def block(self):
        if self._blocked:
            logger.tdebug("timer.info.task.freezed", task=self._get_function_name())
        else:
            logger.tdebug("timer.info.task.freezing", task=self._get_function_name())
        self._blocked = True
        if self._cur_task is not None:
            self._cur_task.cancel()
            self._cur_task = None
        if self._task is not None:
            self._task.cancel()
            self._task = None

    def _run(self):
        if self._blocked or not int(os.environ["ASYNCIO_STARTUP"]):
            return
        interval = self._interval if self._called else self._delay
        self._called = True
        self._cur_task = asyncio.get_event_loop().call_later(
            interval,
            lambda: asyncio.run_coroutine_threadsafe(
                self.run(), asyncio.get_event_loop()
            ),
        )
        # logger.debug(f"The task <{self._get_function_name()}> is next called in {interval:.2f} seconds.")

    async def _call_async(self):
        try:
            if inspect.iscoroutinefunction(self._handler):
                await self._handler(*self._args, **self._kwargs)
            elif inspect.iscoroutine(self._handler):
                await self._handler
        except:
            logger.error(traceback.format_exc())

    def _call_sync(self):
        try:
            self._handler(*self._args, **self._kwargs)
        except:
            logger.error(traceback.format_exc())

    async def run(self):
        try:
            if inspect.iscoroutinefunction(self._handler) or inspect.iscoroutine(
                self._handler
            ):
                self._task = asyncio.create_task(self._call_async())
            else:
                self._task = await asyncio.get_event_loop().run_in_executor(
                    None, self._call_sync
                )
        except:
            logger.error(traceback.format_exc())
        self._run()


def parse_filename(filename: str):
    name = filename.lower().removeprefix(ROOT.lower())
    if name != filename:
        name = name.replace("\\", "/").replace("/", ".").lstrip(".").rstrip(".py")
    else:
        name = filename
    return name


"""class Task:
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


Timer: TimerManager = TimerManager()"""


def delay(
    handler: Callable,
    args: Optional[tuple] = (),
    kwargs: Optional[dict[str, Any]] = {},
    delay: float = 1,
):
    task = Task(handler=handler, args=args, kwargs=kwargs, delay=delay)
    task._run()
    return task


def repeat(
    handler: Callable,
    args: Optional[tuple] = (),
    kwargs: Optional[dict[str, Any]] = {},
    delay: float = 1,
    interval: float = 1,
):
    task = Task(
        handler=handler, args=args, kwargs=kwargs, delay=delay, interval=interval
    )
    task._run()
    return task
