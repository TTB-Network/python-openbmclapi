from pathlib import Path
import tempfile
import time
import anyio.abc

from core.abc import ResponseFile, ResponseFileLocal, ResponseFileNotFound
from ..logger import logger

from .abc import FileInfo, Storage


class LocalStorage(Storage):
    type = "local"
    def __init__(
        self,
        name: str,
        path: str,
        weight: int,
        **kwargs
    ):
        super().__init__(name, path, weight)

    async def setup(
        self,
        task_group: anyio.abc.TaskGroup
    ):
        await super().setup(task_group)

        path = Path(str(self.path))
        path.mkdir(parents=True, exist_ok=True)

        task_group.start_soon(self._check)

    async def list_files(
        self,
        path: str
    ) -> list[FileInfo]:
        root = Path(str(self.path)) / path
        res = []
        # only files
        if not root.exists():
            return []
        for file in root.iterdir():
            if not file.is_file():
                continue
            res.append(FileInfo(
                name=file.name,
                size=file.stat().st_size,
                path=str(file.relative_to(root))
            ))
        return res
    
    async def upload(
        self,
        path: str,
        tmp_file: tempfile._TemporaryFileWrapper,
        size: int
    ):
        root = Path(str(self.path)) / path
        root.parent.mkdir(parents=True, exist_ok=True)
        with open(root, "wb") as f:
            while (data := tmp_file.read(65536)):
                if not data:
                    break
                f.write(data)
        return True

    async def _check(
        self,
    ):
        file = Path(str(self.path)) / ".py_check"
        while 1:
            try:
                file.write_text(str(time.perf_counter_ns()))
                file.unlink()
                self.online = True
            except:
                self.online = False
                logger.traceback()
            finally:
                self.emit_status()
                await anyio.sleep(60)
        
    async def get_file(self, path: str) -> ResponseFile:
        p = Path(str(self.path / path))
        if not p.exists():
            return ResponseFileNotFound()
        size = p.stat().st_size
        return ResponseFileLocal(
            size=size,
            path=p
        )
    