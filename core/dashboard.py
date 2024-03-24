from dataclasses import asdict, dataclass
import hashlib
import os
import time
from typing import Any
import zlib

import aiohttp

from core import stats, system, utils, web
from core import cluster
from core.api import StatsCache
from core.config import Config

@dataclass
class Token:
    value: str
    create_at: float

BASE_URL = "https://openbmclapi.bangbang93.com/"
CLUSTER_ID: str = Config.get("cluster.id")
CLUSTER_SECERT: str = Config.get("cluster.secret")
last_status = ""
tokens: list[Token] = []
def deserialize(data: utils.DataInputStream):
    match (data.readVarInt()):
        case 0:
            return data.readString()
        case 1:
            return data.readBoolean()
        case 2:
            return int(data.readString())
        case 3:
            return float(data.readString())
        case 4:
            return [deserialize(data) for _ in range(data.readVarInt())]
        case 5:
            return {deserialize(data): deserialize(data) for _ in range(data.readVarInt())}
        case 6:
            return None
def serialize(data: Any):
    buf = utils.DataOutputStream()
    if isinstance(data, str):
        buf.writeVarInt(0)
        buf.writeString(data)
    elif isinstance(data, bool):
        buf.writeVarInt(1)
        buf.writeBoolean(data)
    elif isinstance(data, float):
        buf.writeVarInt(2)
        buf.writeString(str(data))
    elif isinstance(data, int):
        buf.writeVarInt(3)
        buf.writeString(str(data))
    elif isinstance(data, list):
        buf.writeVarInt(4)
        buf.writeVarInt(len(data))
        buf.write(b''.join((serialize(v).io.getvalue() for v in data)))
    elif isinstance(data, dict):
        buf.writeVarInt(5)
        buf.writeVarInt(len(data.keys()))
        buf.write(b''.join((serialize(k).io.getvalue() + serialize(v).io.getvalue() for k, v in data.items())))
    elif data == None:
        buf.writeVarInt(6)
    return buf
async def process(type: str, data: Any):
    if type == "runtime":
        return float(os.getenv("STARTUP") or 0)
    if type == "dashboard":
        return {"hourly": stats.hourly(), "days": stats.daily()}
    if type == "qps":
        c = web.statistics.get_time()
        c -= 610
        return {k: v for k, v in web.statistics.get_all_qps().items() if k > c}
    if type == "status":
        return last_status
    if type == "master":
        async with aiohttp.ClientSession(BASE_URL) as session:
            async with session.get(data) as resp:
                return resp.json()
    if type == "system":
        return {
            "memory": system.get_used_memory(),
            "connections": system.get_connections(),
            "cpu": system.get_cpus(),
            "cache": asdict(await cluster.cluster.get_cache_stats()) if cluster.cluster else StatsCache()
        }
async def set_status(text):
    global last_status 
    if last_status != text:
        app = web.app
        output = to_bytes("status", text)
        for ws in app.get_websockets("/bmcl/"):
            await ws.send(output.io.getvalue())
    last_status = text

def to_bytes(type: str, data: Any):
    output = utils.DataOutputStream()
    output.writeString(type)
    output.write(serialize(data).io.getvalue())
    return output

def generate_token(request: 'web.Request') -> Token:
    global tokens
    token = Token(hashlib.sha256(zlib.compress(hashlib.sha512((request.get_ip() + request.get_user_agent() + request.get_url() + CLUSTER_ID + CLUSTER_SECERT + str(time.time())).encode("utf-8")).digest())).hexdigest(), time.time())
    tokens.append(token)
    return token

def token_isvaild(value) -> bool:
    for token in tokens:
        if token.value == value and token.create_at + 86400 > time.time():
            return True
    return False