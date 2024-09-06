import asyncio
from collections import deque
import hashlib
import io


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
                if fut in self.fut:
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
    
class SemaphoreLock:
    def __init__(self, value: int):
        self._value = value
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
                if fut in self.fut:
                    self.fut.remove(fut)
    
    async def acquire(self):
        if self.count >= self._value:
            await self.wait()
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
    
    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
    
    def set_value(self, value: int):
        self._value = value
    
                    
    

class FileStream:
    def __init__(self, data: bytes) -> None:
        self.data = io.BytesIO(data)
    
    def read_long(self): 
        result, shift = 0, 0
        while True:
            byte = ord(self.data.read(1))
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
        return (result >> 1) ^ -(result & 1)
    def read_string(self):
        return self.data.read(self.read_long()).decode('utf-8')
    

def equals_hash(origin: str, content: bytes):
    return get_hash_hexdigest(origin, content) == origin

def get_hash_hexdigest(origin: str, content: bytes):
    h = hashlib.sha1
    if len(origin) == 32:
        h = hashlib.md5
    return h(content).hexdigest()