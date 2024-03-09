<<<<<<< HEAD
import importlib
import subprocess

def install_module(module_name, module = None):
    module = module or module_name
    try:
        importlib.import_module(module_name)
    except ImportError:
        print(f"正在安装模块 '{module_name}'...")
        subprocess.check_call(["pip", "install", module])
        print(f"模块 '{module_name}' 安装成功")

def init():
    install_module('socketio')
    install_module('aiohttp')
    install_module("hmac")
    install_module("pyzstd")
    install_module("avro", "avro-python3")

init()

if __name__ == "__main__":
    import web
    web.init()
=======
import asyncio
from pathlib import Path
import ssl
import traceback
from typing import Optional
import config
from utils import Client
import web
server: Optional[asyncio.Server] = None
cert = None

def load_cert():
    global cert
    if Path(".ssl/cert.pem").exists() and Path(".ssl/key.pem").exists():
        cert = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        cert.check_hostname = False
        cert.load_cert_chain(Path(".ssl/cert.pem"), Path(".ssl/key.pem"))
        if server:
            server.close()

async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    client = Client(reader, writer)
    timeout = config.TIMEOUT
    try:
        while (type := await client.readuntil(b"\r\n", timeout=timeout)):
            if b'HTTP/1.1' in type:
                await web.handle(type, client)
            timeout = 10
    except (TimeoutError, asyncio.exceptions.IncompleteReadError) as e:
        ...
    except:
        traceback.print_exc()
async def main():
    global cert, server
    load_cert()
    try:
        server = await asyncio.start_server(_handle, host='0.0.0.0', port=config.PORT, ssl=cert)
        print(f"Server listen on {config.PORT}{' with ssl' if cert else ''}!")
        import cluster
        await cluster.init()
        await server.serve_forever()
    except:
        if server:
            server.close()
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
>>>>>>> 1821e9a699e53437109088d3d8cf4bb4a1bf9a50
