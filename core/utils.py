import asyncio
from collections import deque


class CountLock:
    def __init__(self):
        self.count = 0
        self.fut: deque[asyncio.Future] = deque()
    
    async def wait(self):
        if self.count >= 1:
            fut = asyncio.get_running_loop().create_future()
            self.fut.append(fut)
            try:
                await fut
            except asyncio.CancelledError:
                raise
            finally:
                self.fut.remove(fut)
    
    def acquire(self):
        self.count += 1
    
    def release(self):
        self.count -= 1
        if self.count == 0 and self.fut:
            self._wake()

    def _wake(self):
        if self.fut:
            for fut in self.fut:
                try:
                    fut.set_result(None)
                except asyncio.InvalidStateError:
                    pass
            self.fut.clear()

    @property
    def locked(self):
        return self.count > 0