import abc
import asyncio
import re
from typing import Optional

class TunnelConfiguration:
    @property
    def timeout(self):
        return 30
    

class BaseTunnel(metaclass=abc.ABCMeta):
    """
    Base tunnel class
    """

    type = "abstract"

    @abc.abstractmethod
    async def start_service(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def stop_service(self):
        raise NotImplementedError
    
    @abc.abstractmethod
    async def get_host(self):
        raise NotImplementedError
    
    @abc.abstractmethod
    async def get_port(self):
        raise NotImplementedError
    

class ShellTunnel(BaseTunnel):
    type = "shell"

    def __init__(self, cmd: str, output_regex: str):
        self.program: Optional[asyncio.subprocess.Process] = None
        self.cmd = cmd
        self.output_regex = re.compile(output_regex)

    async def start_service(self):
        self.program = await asyncio.create_subprocess_shell(
            self.cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def stop_service(self):
        if self.program:
            self.program.terminate()
            await self.program.wait()

    async def get_host(self):
        if self.program:
            stdout, _ = await self.program.communicate()
            match = self.output_regex.search(stdout.decode())
            if match:
                return match.group(1)

    async def get_port(self):
        if self.program:
            stdout, _ = await self.program.communicate()
            match = self.output_regex.search(stdout.decode())
            if match:
                return match.group(2)
        return None
    
