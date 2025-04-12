from collections import defaultdict, deque
from dataclasses import dataclass
import datetime
from typing import Any, Optional
import anyio
import anyio.abc
from bson import ObjectId
import fastapi
import psutil
from fastapi.staticfiles import StaticFiles

from .config import ROOT_PATH
from .web import query_per_second_statistics
from .utils import scheduler
from tianxiu2b2t.utils import runtime


class StreamNotice:
    def __init__(
        self
    ):
        self.clients: defaultdict[fastapi.Request, ObjectId] = defaultdict(lambda: ObjectId('0' * 24))
        self.events: defaultdict[fastapi.Request, anyio.Event] = defaultdict(anyio.Event)

    def add_client(self, request: fastapi.Request) -> fastapi.responses.StreamingResponse:
        return fastapi.responses.StreamingResponse(
            self.stream(request),
            media_type="text/event-stream",
        )

    async def stream(self, request: fastapi.Request):
        try:
            while not await request.is_disconnected():
                yield ''
        except:
            ...
    
    async def put(self, event: str, data: Any):
        ...

@dataclass
class MemoryInfo:
    rss: int
    vms: int

class SystemInfo:
    def __init__(
        self
    ):
        self.process = psutil.Process()
        self.cpus: deque[float] = deque(maxlen=600)
        self.memory: deque[MemoryInfo] = deque(maxlen=600)
        self._running = 0

    def setup(
        self,
    ):
        self._running = 1
        scheduler.add_job(
            self.update,
            trigger="date",
            next_run_time=datetime.datetime.now(),
            id="systeminfo"
        )
        
    def stop(
        self,
    ):
        self._running = 0

    def update(
        self,
    ):
        while self._running:
            try:
                self.cpus.append(self.process.cpu_percent(interval=1))

                memory = self.process.memory_full_info()

                self.memory.append(MemoryInfo(
                    rss=memory.rss,
                    vms=memory.vms,
                ))
            except:
                break

    def get_info(self) -> dict[str, Any]:
        return {
            "cpu": self.cpus[-1] if self.cpus else 0,
            "memory": self.memory[-1] if self.memory else MemoryInfo(0, 0),
            "sysload": psutil.getloadavg(),
            "load": sum(self.cpus) / len(self.cpus) if self.cpus else 0,
            "process_runtime": runtime.perf_counter(),
        }

notice = StreamNotice()

systeminfo = SystemInfo()

async def setup(
    app: fastapi.FastAPI,
    task_group: anyio.abc.TaskGroup,
):
    #if not DEBUG:
    #    return

    systeminfo.setup()

    @app.get("/favicon.ico")
    def _():
        return fastapi.responses.FileResponse(
            ROOT_PATH / "assets" / "favicon.ico",
        )

    app.mount("/assets", StaticFiles(directory=ROOT_PATH / "assets"), name="assets")

    @app.get("/api/receive")
    async def _(request: fastapi.Request):
        return notice.add_client(request)
    
    @app.get("/api/qps")
    async def _(request: fastapi.Request, interval: Optional[int] = 5):
        if interval is None:
            return query_per_second_statistics.get_all()
        return query_per_second_statistics.merge_data(interval)
    
    @app.get("/api/system")
    async def _():
        return systeminfo.get_info()

    @app.get("/")
    @app.get("/{page}")
    @app.get("/{page}/{pages}")
    def index():
        return fastapi.responses.FileResponse(
            ROOT_PATH / "assets" / "index.html",
        )
    

def stop(
):
    systeminfo.stop()