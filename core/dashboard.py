import asyncio
from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json
import sys
import time
from typing import Any, Optional
import zlib

import aiohttp
from tqdm import tqdm

from core import statistics, system, update, utils, web
from core import cluster
from core.api import StatsCache
from core import scheduler
import psutil
from core.const import *
from core.env import env


@dataclass
class Token:
    value: str
    create_at: float


@dataclass
class StorageInfo:
    name: str
    type: str
    endpoint: str
    size: int
    free: int


@dataclass
class ProgressBar:
    object: Optional[tqdm] = None
    desc: str = ""
    last_value: float = 0
    speed: float = 0
    show: Optional[int] = None


websockets: list["web.WebSocket"] = []
last_status = ""
last_text = ""
cur_tqdm: ProgressBar = ProgressBar()
task_tqdm: Optional[int] = None
tokens: list[Token] = []
authentication_module: list[str] = [
    "storages",
    "version",
]


def parse_json(data: tuple | set | dict | Any):
    if isinstance(data, (list, tuple, set)):
        return [parse_json(data) for data in data]
    elif is_dataclass(data):
        return parse_json(asdict(data))
    elif isinstance(data, dict):
        return {parse_json(k): parse_json(v) for k, v in data.items()}
    return data


async def process(type: str, data: Any):
    if type == "statistics":
        return statistics.get_storage_stats(data)
    if type == "qps":
        c = web.statistics.get_time()
        c -= c % 5
        raw_data = {
            k: v for k, v in web.statistics.get_all_qps().items() if k > c - 300
        }
        return {
            utils.format_time(i + -time.timezone): (sum((raw_data.get(i + j, 0) for j in range(5))))
            for i in range(c - 300, c, 5)
        }
    if type == "status":
        resp = {
            "key": last_status,
            "uptime": float(env["STARTUP"] or 0),
            "timestamp": data,
            "time": {
                "current": time.time(),
                "offset_utc": -(time.timezone / 3600)
            }
        }
        if cur_tqdm is not None and cur_tqdm.object is not None:
            if cur_tqdm.object is None or cur_tqdm.object.disable:
                scheduler.cancel(task_tqdm)
                scheduler.cancel(cur_tqdm.show)
                cur_tqdm.object = None
            if cur_tqdm.object is not None:
                resp.update(
                    {
                        "progress": {
                            "value": cur_tqdm.object.n,
                            "total": cur_tqdm.object.total,
                            "speed": cur_tqdm.speed,
                            "unit": cur_tqdm.object.unit,
                            "desc": cur_tqdm.desc,
                            "postfix": cur_tqdm.object.postfix,
                            "start": utils.format_stime(time.time() - cur_tqdm.object.start_t),
                            "end": utils.format_stime(((cur_tqdm.object.total - cur_tqdm.object.n) / cur_tqdm.speed)) if cur_tqdm.speed != 0 else utils.format_stime(None)
                        }
                    }
                )
        return resp
    if type == "master":
        async with aiohttp.ClientSession(BASE_URL) as session:
            async with session.get(data) as resp:
                return await resp.json()
    if type == "system":
        return {
            "memory": system.get_used_memory(),
            "connections": system.get_connections(),
            "cpu": system.get_cpus(),
            "cache": (
                asdict(get_cache_stats() if cluster.cluster else StatsCache())
            ),
        }
    if type == "version":
        return {
            "cur": update.VERSION,
            "latest": update.fetched_version,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }
    if type == "pro_stats" or type == "geo_stats":
        day = 1
        if isinstance(data, dict):
            t = data.get("type", 0)
            if t == 1:
                day = 7
            elif t == 2:
                day = 30
            elif t >= 3:
                day = -1
        func = statistics.stats_pro if type == "pro_stats" else statistics.geo_pro
        return await asyncio.get_event_loop().run_in_executor(None, func, day)
    
    if type == "system_details":
        return system.get_loads_detail()
    
    if type == "unknown_addresses":
        unknown = await asyncio.get_event_loop().run_in_executor(None, statistics.get_unknown_ip)
        if data is not None:
            with open("ignore.txt", "w", encoding="utf-8") as w:
                w.write('\n'.join(unknown))
        return unknown
    
    if type == "summary_basic":
        return statistics.summary_basic()


def get_cache_stats() -> StatsCache:
    return cluster.cluster.storage_cache_stats()


async def set_status_by_tqdm(text: str, pbar: tqdm):
    global cur_tqdm, task_tqdm
    cur_tqdm.object = pbar
    cur_tqdm.desc = text
    scheduler.cancel(task_tqdm)
    scheduler.cancel(cur_tqdm.show)
    cur_tqdm.speed = 0
    cur_tqdm.last_value = 0
    task_tqdm = scheduler.repeat(_calc_tqdm_speed, delay=0, interval=1)
    cur_tqdm.show = scheduler.repeat(
        _set_status, kwargs={"blocked": True}, delay=0, interval=1
    )


async def _calc_tqdm_speed():
    global cur_tqdm
    if cur_tqdm.object is None or cur_tqdm.object.disable:
        scheduler.cancel(task_tqdm)
        scheduler.cancel(cur_tqdm.show)
        cur_tqdm.object = None
        await _set_status(blocked=True)
        return
    cur_tqdm.speed = cur_tqdm.object.n - cur_tqdm.last_value
    cur_tqdm.last_value = cur_tqdm.object.n


async def _set_status(text: Optional[str] = None, blocked: bool = False):
    global last_text, last_status
    if not text:
        text = last_text
    if last_status == text and not blocked:
        return
    last_status = text
    await trigger("status")


async def set_status(text):
    global last_text
    if last_text != text:
        await _set_status(text)
    last_text = text


async def trigger(type: str, data: Any = None):
    for ws in websockets:
        await ws.send({
            'id': 0,
            'namespace': type,
            'data': await process(type, data)
        })


async def generate_token(request: "web.Request") -> Token:
    global tokens
    token = Token(
        hashlib.sha256(
            zlib.compress(
                hashlib.sha512(
                    (
                        await request.get_ip()
                        + request.get_user_agent()
                        + request.get_url()
                        + CLUSTER_ID
                        + CLUSTER_SECERT
                        + str(time.time())
                    ).encode("utf-8")
                ).digest()
            )
        ).hexdigest(),
        time.time(),
    )
    tokens.append(token)
    return token


def token_isvaild(value) -> bool:
    for token in tokens:
        if token.value == value and token.create_at + 86400 > time.time():
            return True
    return False
