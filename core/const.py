from dataclasses import dataclass
import os
from pathlib import Path
from core.config import Config

VERSION = ""
version_path = Path("VERSION")
if version_path.exists():
    with open(Path("VERSION"), "r", encoding="utf-8") as f:
        VERSION = f.read().split("\n")[0]
        f.close()
else:
    VERSION = "Unknown"
ROOT = os.getcwd()
API_VERSION = "1.10.3"
USER_AGENT = f"openbmclapi-cluster/{API_VERSION} python-openbmclapi/{VERSION}"
BASE_URL = Config.get("cluster.url", "https://openbmclapi.bangbang93.com/")
CLUSTER_ID: str = Config.get("cluster.id")
CLUSTER_SECERT: str = Config.get("cluster.secret")
IO_BUFFER: int = Config.get("advanced.io_buffer")
MAX_DOWNLOAD: int = max(1, Config.get("download.threads"))
BYOC: bool = Config.get("cluster.byoc")
PUBLIC_HOST: str = Config.get("cluster.public_host")
PUBLIC_PORT: int = Config.get("cluster.public_port")
PORT: int = Config.get("web.port")
ENABLE: bool = Config.get("cluster.enable")
RECONNECT_DELAY: bool = Config.get("cluster.reconnect.delay")
RECONNECT_RETRY: bool = Config.get("cluster.reconnect.retry")
ENABLE_TIMEOUT: bool = Config.get("cluster.timeout.enable")
KEEPALIVE_TIMEOUT: bool = Config.get("cluster.timeout.keepalive")
CACHE_BUFFER: int = Config.get("cache.buffer")  # bytes
CACHE_TIME: int = Config.get("cache.time")
CHECK_CACHE: int = Config.get("cache.check")
SIGN_SKIP: bool = Config.get("cluster.skip_sign")
DASHBOARD_USERNAME: str = Config.get("dashboard.username")
DASHBOARD_PASSWORD: str = Config.get("dashboard.password")
TIMEOUT: int = Config.get("advanced.timeout")
REQUEST_BUFFER: int = Config.get("advanced.request_buffer")
FILE_REDIRECTS = ["index.html", "index.htm", "default.html", "default.htm"]
RESPONSE_HEADERS = {
    "Server": Config.get("web.server_name"),
}
RESPONSE_DATE = "%a, %d %b %Y %H:%M:%S GMT"
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
FILECHECK = Config.get("clueset.file_check_mode")
STORAGES: list["StorageParse"] = []


@dataclass
class StorageParse:
    name: str
    type: str
    path: str
    kwargs: dict


if Config.get("storages") is not None:
    for name in Config.get("storages"):
        storage = Config.get(f"storages.{name}")
        STORAGES.append(StorageParse(name, storage["type"], storage["path"], storage))
