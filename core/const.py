from dataclasses import dataclass
import gzip
import os
from pathlib import Path
import re
from typing import Any
import zlib

import pyzstd
from core.config import Config

VERSION = ""
version_path = Path("VERSION")
if version_path.exists():
    with open(Path("VERSION"), "r", encoding="utf-8") as f:
        VERSION = f.read().split("\n")[0]
        f.close()
else:
    VERSION = "Unknown"
CACHE_BUFFER_COMPRESSION_MIN_LENGTH: int = 64
DEBUG: bool = Config.get("advanced.debug")
ROOT: str = os.getcwd()
API_VERSION: str = "1.10.6"
USER_AGENT: str = f"openbmclapi-cluster/{API_VERSION} python-openbmclapi/{VERSION}"
BASE_URL: str = Config.get("advanced.url", "https://openbmclapi.bangbang93.com/")
BD_URL: str = BASE_URL.replace("openbmclapi", "bd")
CLUSTER_ID: str = Config.get("cluster.id")
CLUSTER_SECERT: str = Config.get("cluster.secret")
IO_BUFFER: int = Config.get("advanced.io_buffer")
MAX_DOWNLOAD: int = max(1, Config.get("advanced.download_threads"))
BYOC: bool = Config.get("cluster.byoc")
PUBLIC_HOST: str = Config.get("cluster.public_host")
PUBLIC_PORT: int = Config.get("cluster.public_port")
PORT: int = Config.get("web.port")
RECONNECT_DELAY: bool = max(60, Config.get("cluster.reconnect.delay"))
RECONNECT_RETRY: bool = Config.get("cluster.reconnect.retry")
ENABLE: bool = Config.get("cluster.enable")
ENABLE_TIMEOUT: bool = Config.get("cluster.timeout.enable")
WEBDAV_TIMEOUT: int = 10
KEEPALIVE_TIMEOUT: bool = Config.get("cluster.timeout.keepalive")
CACHE_BUFFER: int = Config.get("cache.buffer")  # bytes
CACHE_TIME: int = Config.get("cache.time")
CHECK_CACHE: int = Config.get("cache.check")
CACHE_ENABLE: int = Config.get("cache.enable")
SIGN_SKIP: bool = Config.get("advanced.skip_sign")
DASHBOARD_USERNAME: str = Config.get("dashboard.username")
DASHBOARD_PASSWORD: str = Config.get("dashboard.password")
DASHBOARD_WEBSOCKET: bool = Config.get("dashboard.websocket")
LIMIT_SESSION_WEBDAV: int = 512
TIMEOUT: int = Config.get("advanced.timeout")
REQUEST_BUFFER: int = Config.get("advanced.request_buffer")
FILE_REDIRECTS: list[str] = ["index.html", "index.htm", "default.html", "default.htm"]
RESPONSE_HEADERS = {
    "Server": Config.get("web.server_name"),
}
CLUSTER_PATTERN = re.compile(r'https?://([a-fA-F0-9]*)\.openbmclapi\.933\.moe(:\d+)/')
DOWNLOAD_ACCESS_LOG: bool = True
DOWNLOAD_RETRY_DELAY: int = 60
DOWNLOAD_FILE: bool = False
DOWNLOAD_CONFIGURATION: bool = True
RESPONSE_DATE = "%a, %d %b %Y %H:%M:%S GMT"
RESPONSE_COMPRESSION_IGNORE_SIZE_THRESHOLD: int = 16777216
SKIP_FILE_CHECK: bool = False
STATUS_CODES: dict[int, str] = {
    100: "Continue",
    101: "Switching Protocols",
    200: "OK",
    201: "Created",
    202: "Accepted",
    203: "Non-Authoritative Information",
    204: "No Content",
    205: "Reset Content",
    206: "Partial Content",
    300: "Multiple Choices",
    301: "Moved Pemanently",
    302: "Found",
    303: "See Other",
    304: "Not Modified",
    305: "Use Proxy",
    306: "Unused",
    307: "Temporary Redirect",
    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    407: "Proxy Authentication Required",
    408: "Request Time-out",
    409: "Conflict",
    410: "Gone",
    411: "Length Required",
    412: "Precondition Failed",
    413: "Request Entity Too Large",
    414: "Request-URI Too Large",
    415: "Unsupported Media Type",
    416: "Requested range not satisfiable",
    417: "Expectation Failed",
    418: "I'm a teapot",
    421: "Misdirected Request",
    422: "Unprocessable Entity",
    423: "Locked",
    424: "Failed Dependency",
    425: "Too Early",
    426: "Upgrade Required",
    428: "Precondition Required",
    429: "Too Many Requests",
    431: "Request Header Fields Too Large",
    451: "Unavailable For Legal Reasons",
    500: "Internal Server Eror",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Time-out",
    505: "HTTP Version not supported",
}
REQUEST_TIME_UNITS = ["ns", "ms", "s", "m", "h"]
FILECHECK = Config.get("advanced.file_check_mode")
X_FORWARDED_FOR: int = Config.get("web.x_forwarded_for")
STORAGES: list["StorageParse"] = []
COMPRESSOR: dict[str, Any] = {
    "zstd": pyzstd.compress,
    "gzip": gzip.compress,
    "deflate": zlib.compress,
}
LANG: str = Config.get("advanced.language")
FORCE_SSL: bool = Config.get("web.force_ssl")
MAX_INSTANCES: int = 9999
AUTO_DOWNLOAD_RELEASE: bool = Config.get("update.auto_download")
COPY_FROM_OTHER_STORAGE: bool = Config.get("advanced.copy_from_another_storage")
DASHBOARD_CONFIGURATION: dict = {
    "websocket": DASHBOARD_WEBSOCKET
}

@dataclass
class StorageParse:
    name: str
    type: str
    path: str
    width: int
    kwargs: dict

@dataclass
class Certificate:
    cert: str = ""
    path: str = ""

if Config.get("storages") is not None:
    for name in Config.get("storages"):
        storage = Config.get(f"storages.{name}")
        STORAGES.append(
            StorageParse(
                name, storage["type"], storage["path"], storage.get("width", 0), storage
            )
        )

CERTIFICATE = Certificate(Config.get("certificate.cert"), Config.get("certificate.key"))

# xdb 默认参数
XDB_HeaderInfoLength = 256
XDB_VectorIndexRows = 256
XDB_VectorIndexCols = 256
XDB_VectorIndexSize = 8
XDB_SegmentIndexSize = 14
