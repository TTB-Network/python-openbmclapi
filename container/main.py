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