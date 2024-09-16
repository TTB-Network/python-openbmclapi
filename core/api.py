from core.orm import *
from aiohttp import web
from core.config import Config
import toml
import os
import platform
import psutil

API_VERSION = Config.get("advanced.api_version")
VERSION = toml.loads(open("pyproject.toml", "r").read())["tool"]["poetry"]["version"]


async def getStatus(cluster) -> web.Response:
    hourly_hits = getHourlyHits()
    daily_hits = getDailyHits()
    monthly_hits = getMonthlyHits()
    agent_info = getAgentInfo()
    response = {
        "status": int(cluster.enabled),
        "startTime": cluster.start_time,
        "stats": {
            "hours": hourly_hits["stats"],
            "days": daily_hits["stats"],
            "months": monthly_hits["stats"],
        },
        "prevStats": {
            "hours": hourly_hits["prevStats"],
            "days": daily_hits["prevStats"],
            "months": monthly_hits["prevStats"],
        },
        "accesses": agent_info,
        "connections": cluster.router.connection if cluster.router else 0,
        "memory": psutil.Process(os.getpid()).memory_info().rss,
        "cpu": psutil.Process(os.getpid()).cpu_percent(),
        "pythonVersion": platform.python_version(),
        "apiVersion": API_VERSION,
        "version": VERSION,
    }
    return web.json_response(data=response)
