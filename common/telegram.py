import asyncio
from collections import deque
import time
from typing import Any, Optional

import aiohttp

from .logger import logger
from .env import env
from .timings import Timings
from .units import format_count_time

import urllib.parse as urlparse

class TelegramBot:
    def __init__(
        self,
        token: str,
        channel_id: Optional[int] = None,
        http_proxy: Optional[str] = None
    ):
        self.token = token
        self.url = f"https://api.telegram.org/bot{self.token}/"
        self.http_proxy = http_proxy
        self.channel_id = channel_id
        self.tasks: deque[asyncio.Task[Any]] = deque()
        self.sem = asyncio.Semaphore(2)

    async def post_message(self, message: str):
        return 
        async with aiohttp.ClientSession(
            proxy=self.http_proxy
        ) as session, self.sem:
            start = time.monotonic()
            async with session.post(
                urlparse.urljoin(
                    self.url,
                    "sendMessage"
                ),
                json={
                    "chat_id": self.channel_id,
                    "text": message
                }
            ) as resp:
                data = await resp.json()
                status = data['ok']
                if not status:
                    logger.debug(f"post_message {status}: {data}")
            await asyncio.sleep(max(1.5, time.monotonic() - start))

    def post_status(
        self,
        status: str,
        title: str,
        *content: str
    ) -> list[asyncio.Task]:
        def done(x: asyncio.Task):
            nonlocal tasks
            tasks.remove(x)
            self.tasks.remove(x)
            if tasks:
                return
            timings.end()
            logger.debug(f"post_status: {status} -> {title} done, total {format_count_time(timings.get_duration() or 0)}")
        timings = Timings()
        timings.start()
        tasks = []
        message = f"{status} -> {title}\n\n"
        for _ in range(0, len(content), 20):
            msg = message + "\n".join(content[_:_+20])
            task = asyncio.create_task(self.post_message(msg))
            task.add_done_callback(lambda x: done(x))
            tasks.append(task)
            self.tasks.append(task)
        return tasks
        
        
    async def wait_post_status(
        self,
        status: str,
        title: str,
        *content: str
    ) -> list[Any]:
        results = []
        message = f"{status} -> {title}\n\n"
        for _ in range(0, len(content), 20):
            msg = message + "\n".join(content[_:_+20])
            results.append(await self.post_message(msg))
        logger.debug(f"post_status: {results}")
        return results
    
    async def wait_closed(self):
        while self.tasks:
            await self.tasks.popleft()
            

bot = TelegramBot(env.get('TELEGRAM_BOT_TOKEN') or "", -1002369661065, env.get('HTTP_PROXY'))