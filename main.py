import ssl
import zlib
import asyncio
from enum import Enum
from pathlib import Path
import random
import time
from typing import Any, Optional
import cluster
from utils import Client, info, traceback
import utils
import globals
import web
import os

os.environ['TMPDIR'] = str(Path(str(Path(__file__).absolute().parent) + "/cache"))
os.environ['STARTUP'] = str(time.time())
detect_key = random.randbytes(8)
class ProtocolHeader(Enum):
    HTTP = 'HTTP'
    NONE = 'Unknown'
    DETECTKEY = "Detect"
    GZIP = "Gzip"
    @staticmethod
    def from_data(data: bytes):
        if detect_key == data:
            return ProtocolHeader.DETECTKEY
        if b'HTTP/1.1\r\n' in data or b'HTTP/1.0\r\n' in data:
            return ProtocolHeader.HTTP
        
        try:
            zlib.decompress(data)
            return ProtocolHeader.GZIP
        except:
            ...
        return ProtocolHeader.NONE
    def __str__(self) -> str:
        return self.value
    def __repr__(self) -> str:
        return self.value
ports: dict[int, asyncio.Server] = {}
port_: list[int] = [8800]
started_port: list[int] = []
protocol_handler: dict[ProtocolHeader, Any] = {}
protocol_startup: dict[ProtocolHeader, Any] = {}
protocol_shutdown: dict[ProtocolHeader, Any] = {}

async def handle(client: Client):
    protocol: Optional[ProtocolHeader] = None
    try:
        while (data := await client.read(8192)) and not client.is_closed():
            if not data:
                break
            if not protocol:
                protocol = ProtocolHeader.from_data(data)
            if protocol == ProtocolHeader.DETECTKEY:
                client.write(data)
                break
            if protocol == ProtocolHeader.GZIP:
                client.compressed = True
                protocol = ProtocolHeader.from_data(data)
            if protocol_handler.get(protocol) != None:
                await protocol_handler[protocol](data, client)
            if not client.keepalive_connection:
                break
            client.set_log_network(None)
    except:
        traceback(False)
    client.close()

async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    client = Client(reader, writer)
    if cert:
        client.is_ssl = True
    try:
        await asyncio.wait([asyncio.create_task(handle(client))], timeout=globals.TIMEOUT)
    except TimeoutError:
        client.close()
cert = None
def load_cert():
    global cert
    if Path("./config/cert.pem").exists() and Path("./config/key.pem").exists():
        cert = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        cert.check_hostname = False
        cert.load_cert_chain("./config/cert.pem", "./config/key.pem")
load_cert()
def get_ports():
    global port_
    return port_
async def start_server(port: int):
    global ports
    try:
        if cert:
            ports[port] = await asyncio.start_server(_handle, port=port, host='0.0.0.0', ssl=cert)
        else:
            ports[port] = await asyncio.start_server(_handle, port=port, host='0.0.0.0')
        for sock in ports[port].sockets:
            sock._sock.settimeout(globals.TIMEOUT)  # type: ignore
        info(f"Started service on {port}{' with ssl' if cert else ''}!")
    except:
        traceback()

async def detect_port(port: int):
    try:
        if cert:
            ccert = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            ccert.check_hostname = False
            ccert.load_verify_locations("./config/cert.pem")
            r, w = await asyncio.open_connection('127.0.0.1', port=port, ssl=ccert)
        else:
            r, w = await asyncio.open_connection('127.0.0.1', port=port)
        w.write(detect_key)
        data = await asyncio.wait_for(r.read(), timeout=5)
        w.close()
        if data != detect_key:
            return False
        return True
    except:
        traceback()
        return False

async def restart_server(port: int):
    while 1:
        while await detect_port(port):
            await asyncio.sleep(5)
        ports[port].close()
        await start_server(port)
        await asyncio.sleep(5)

async def start_():
    start = time.time_ns()
    for port in port_:
        await start_server(port)
    await cluster.init()
    [asyncio.create_task(startup()) for startup in protocol_startup.values() if startup]
    info(f"Done! ({(time.time_ns() - start) / 1000000000.0:.2f}s)")
    await asyncio.wait([asyncio.create_task(restart_server(port)) for port in port_])
    globals.running = 0
    [asyncio.create_task(shutdown()) for shutdown in protocol_shutdown.values() if shutdown]
    async def waiting():
        while any([t for t in utils.threads if t.is_alive()]):
            ...
    info("Waiting 5s in shutdown server.")
    await asyncio.wait_for(waiting(), timeout=5)

def start():
    asyncio.run(start_())

def set_protocol_handler(protocol: ProtocolHeader, handler: Any):
    global protocol_handler
    protocol_handler[protocol] = handler

def set_protocol_startup(protocol: ProtocolHeader, startup: Any):
    global protocol_startup
    protocol_startup[protocol] = startup

def set_protocol_shutdown(protocol: ProtocolHeader, shutdown: Any):
    global protocol_shutdown
    protocol_shutdown[protocol] = shutdown

if __name__ == "__main__":
    set_protocol_handler(ProtocolHeader.HTTP, web.handle)
    if web.application:
        set_protocol_startup(ProtocolHeader.HTTP, web.application.start)
        set_protocol_shutdown(ProtocolHeader.HTTP, web.application.stop)
    start()