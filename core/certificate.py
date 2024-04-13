import os
from pathlib import Path
import ssl
import time
from .i18n import locale
import traceback

from core.logger import logger
import core

ssl_dir = Path(".ssl")
ssl_dir.mkdir(exist_ok=True, parents=True)
server_side_ssl = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
server_side_ssl.check_hostname = False
client_side_ssl = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
client_side_ssl.check_hostname = False

_loaded: bool = False


def load_cert(cert, key):
    global server_side_ssl, client_side_ssl, _loaded
    if not os.path.exists(cert) or not os.path.exists(key):
        return False
    try:
        server_side_ssl.load_cert_chain(cert, key)
        client_side_ssl.load_verify_locations(cert)
        _loaded = True
        return True
    except:
        logger.terror("cert.error.failed", failure=traceback.format_exc())
        return False


def get_loaded() -> bool:
    return _loaded


def load_text(cert: str, key: str):
    t = time.time()
    cert_file = Path(f"./.ssl/{t}_cert")
    key_file = Path(f"./.ssl/{t}_key")
    with open(cert_file, "w") as c, open(key_file, "w") as k:
        c.write(cert)
        k.write(key)
    if load_cert(cert_file, key_file):
        logger.tsuccess("cert.success.loaded_cert")
        core.restart = True
        if core.server:
            core.server.close()
    cert_file.unlink()
    key_file.unlink()
