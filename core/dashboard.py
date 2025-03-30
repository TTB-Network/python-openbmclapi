from collections import defaultdict
from typing import Any, Optional
import anyio
from bson import ObjectId
import fastapi
from fastapi.staticfiles import StaticFiles

from .config import ROOT_PATH, DEBUG
from .web import query_per_second_statistics


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

notice = StreamNotice()
    

async def setup(
    app: fastapi.FastAPI
):
    if not DEBUG:
        return

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

    @app.get("/")
    @app.get("/{page}")
    @app.get("/{page}/{pages}")
    def index():
        return fastapi.responses.FileResponse(
            ROOT_PATH / "assets" / "index.html",
        )