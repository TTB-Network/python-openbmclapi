import asyncio
import base64
import hashlib
import io
import time
from typing import Optional
import urllib.parse as urlparse
import anyio
import fastapi

from tianxiu2b2t import units
from .abc import ResponseFileLocal, ResponseFileMemory, ResponseFileNotFound, ResponseFileRemote
from .locale import load_languages
from .cluster import ClusterManager
from .config import API_VERSION, VERSION, cfg
from .logger import logger
from .utils import runtime
from .database import init as init_database
from .dashboard import setup as setup_dashboard
from . import web
import platform

clusters: 'ClusterManager' = ClusterManager()

def init():
    try:
        anyio.run(main)
    except KeyboardInterrupt:
        pass

def load_storages():
    storages = clusters.storages
    
    for cfg_storage in cfg.get('storages', []):
        try:
            name = cfg_storage['name']
            path = cfg_storage['path']
            type = cfg_storage['type']
            logger.tinfo("core.initialize.storage", name=name, path=path, type=type)
            storages.add_storage(**cfg_storage)
        except KeyError:
            logger.terror("core.initialize.storage.missing", cfg=cfg_storage)
            continue
    
    logger.tinfo("core.initialized.storages", count=len(storages.storages))

def load_clusters():
    for cfg_cluster in cfg.get('clusters', []):
        try:
            id, secret = cfg_cluster['id'], cfg_cluster['secret']
            logger.tinfo("core.initialize.cluster", id=id)
            clusters.add_cluster(id, secret)
        except KeyError as e:
            logger.terror("core.initialize.cluster.missing", err=e)
            continue

async def load_database():
    await init_database(
        cfg.get('database', {})
    )

async def load_config():
    load_storages()
    load_clusters()
    await load_database()

    if clusters.count == 0 or clusters.storages.count == 0:
        logger.terror("core.initialize.missing", clusters=clusters.count, storages=clusters.storages.count)

async def main():
    global clusters

    load_languages()

    logger.tinfo("core.initialize")
    logger.tinfo("core.initialize.version", api_version=API_VERSION, version=VERSION)
    logger.tinfo("core.initialize.platform", os=platform.system(), python=platform.python_version(), arch=platform.architecture()[0])
    
    try:
        async with anyio.create_task_group() as task_group:
            await load_config()

            await utils.event.setup(task_group)

            await clusters.setup(task_group)

            await web.setup(task_group, clusters)

            await setup_dashboard(web.app)

            await clusters.sync()

            # serve
            await clusters.serve()
    except asyncio.CancelledError:
        ...
    except:
        logger.traceback()

    finally:
        await clusters.stop()
        await anyio.sleep(max(0, 5 - runtime.get_perf_counter()))
        logger.tinfo("core.exit")

FORBIDDEN = fastapi.responses.Response(
    status_code=403,
    content="Forbidden"
)

@web.app.get("/measure/{size}")
async def measure(size: int, s: str, e: str):
    cluster_id = get_cluster_from_sign(f"/measure/{size}", s, e)
    if cluster_id is None:
        return FORBIDDEN

    file = None

    if cfg.storage_measure:
        file = await clusters.get_measure_file(size)
    if file is not None and isinstance(file, ResponseFileRemote):
        return fastapi.responses.RedirectResponse(
            file.url,
            status_code=302,
        )
    async def iter():
        for _ in range(size):
            yield b'0' * 1024 * 1024
    return fastapi.responses.StreamingResponse(
        iter(),
        media_type="application/octet-stream"
    )

@web.app.get("/download/{hash}")
async def download(request: fastapi.Request, hash: str, s: str, e: str, name: Optional[str] = None):
    cluster_id = get_cluster_from_sign(hash, s, e)
    if cluster_id is None:
        return FORBIDDEN
    file = await clusters.get_response_file(hash)
    size = file.size
    range = request.headers.get("Range")
    if range:
        size = utils.get_range_size(range, size)

    resp_headers = {}
    if name:
        resp_headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{urlparse.quote(name)}"
    resp_headers["X-BMCLAPI-Hash"] = hash
    resp_headers["X-BMCLAPI-Size"] = str(size)
    clusters.hit(cluster_id, size or 0)

    if isinstance(file, ResponseFileLocal):
        return fastapi.responses.FileResponse(
            file.path,
            headers=resp_headers,
        )
    elif isinstance(file, ResponseFileRemote):
        return fastapi.responses.RedirectResponse(
            file.url,
            status_code=302,
            headers=resp_headers,
        )
    elif isinstance(file, ResponseFileMemory):
        result = b''
        r = utils.parse_range(range or "")
        if r is not None:
            if r.start >= len(file.data) or r.end is not None and (r.end > len(file.data) or r.end < r.start):
                return fastapi.responses.Response(
                    status_code=416,
                    content="Range Not Satisfiable"
                )
        status = 200
        if r is None:
            result = file.data
        elif r.end is None:
            result = file.data[r.start:]
        else:
            result = file.data[r.start:r.end + 1]
        if r is not None:
            status = 206
            resp_headers["Content-Range"] = f"bytes {r.start}-{len(result) + r.start - 1}/{len(file.data)}"
        resp_headers["Content-Length"] = str(len(result))
        return fastapi.responses.StreamingResponse(
            io.BytesIO(result),
            status_code=status,
            headers=resp_headers,
        )
    elif isinstance(file, ResponseFileNotFound):
        return fastapi.responses.Response(
            status_code=404,
            content="Not Found"
        )
    else:
        return fastapi.responses.Response(
            status_code=200,
        )

@web.app.get("/robots.txt")
def _():
    return "User-agent: *\nDisallow: /"

def access_log(request: fastapi.Request, response: fastapi.Response, total_time: int):
    raw_path = request.url.path
    # with query params
    if request.url.query:
        raw_path += "?" + request.url.query
    
    if not config.cfg.access_log and (
        raw_path.startswith("/download/") or raw_path.startswith("/measure/")
    ) and response.status_code in (200, 206, 302):
        return


    address = request.headers.get("X-Real-IP") or ""
    if not address and request.client:
        sockname = (request.client.host, request.client.port)
        address = web.get_origin_address(sockname)[0]
    logger.tinfo(
        "web.access_log",
        host=request.headers.get("Host") or "",
        method=request.method.ljust(7),
        path=raw_path,
        status=response.status_code,
        total_time=units.format_count_time(total_time, 4).rjust(14),
        user_agent=request.headers.get("User-Agent") or "",
        address=address,
    )

@web.app.middleware("http")
async def auth_middleware(request: fastapi.Request, call_next):
    start_time = runtime.get_perf_counter_ns()
    try:
        result = await call_next(request)
    except:
        logger.traceback()
        result = fastapi.responses.Response(
            status_code=500,
            content="Internal Server Error"
        )

    end_time = runtime.get_perf_counter_ns()

    access_log(request, result, end_time - start_time)
    # access log

    return result

def get_cluster_from_sign(hash: str, s: str, e: str) -> Optional[str]:
    for cluster in clusters.clusters:
        if check_sign_without_time(hash, cluster._token._secret, s, e):
            return cluster.id
    return None

def check_sign(hash: str, secret: str, s: str, e: str) -> bool:
    return check_sign_without_time(hash, secret, s, e) and time.time() - 300 < int(e, 36)

def check_sign_without_time(hash: str, secret: str, s: str, e: str):
    if not s or not e:
        return False
    sign = (
        base64.urlsafe_b64encode(
            hashlib.sha1(f"{secret}{hash}{e}".encode()).digest()
        )
        .decode()
        .rstrip("=")
    )
    return sign == s