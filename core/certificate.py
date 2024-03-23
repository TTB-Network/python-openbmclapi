import os
from pathlib import Path
import ssl
import time
import traceback

from core.logger import logger
import core

ssl_dir = Path(".ssl")
ssl_dir.mkdir(exist_ok=True, parents=True)
server_side_ssl = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
server_side_ssl.check_hostname = False
client_side_ssl = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
client_side_ssl.check_hostname = False

_loads: int = 0

def load_cert(cert, key):
    global server_side_ssl, client_side_ssl, _loads
    if not os.path.exists(cert) or not os.path.exists(key):
        return False
    try:
        server_side_ssl.load_cert_chain(cert, key)
        client_side_ssl.load_verify_locations(cert)
        _loads += 1
        return True
    except:
        logger.error("Failed to load certificate: ", traceback.format_exc())
        return False

def get_loads() -> int:
    global _loads
    return _loads

def load_text(cert: str, key: str):
    t = time.time()
    cert_file = Path(f".ssl/{t}_cert")
    key_file = Path(f".ssl/{t}_key")
    with open(cert_file, "w") as c, open(key_file, "w") as k:
        c.write(cert)
        k.write(key)
    if load_cert(cert_file, key_file):
        logger.info("Loaded certificate from text! Current:", get_loads())
        core.restart = True
        if core.server:
            core.server.close()
    cert_file.unlink()
    key_file.unlink()