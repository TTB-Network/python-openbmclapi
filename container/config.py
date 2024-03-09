from pathlib import Path
import yaml
from typing import Union

class CFG:
    def __init__(self, path: str) -> None:
        self.file = Path(path)
        self.cfg = {}
        if self.file.exists():
            self.load()    

    def load(self):
        with open(self.file, "r", encoding="utf-8") as f:
            self.cfg = yaml.load(f.read(), Loader=yaml.FullLoader)

    def get(self, key, default_):
        value = self.cfg.get(key, default_)
        if value is None:
            self.write(key, default_)
        return value

    def write(self, key, value):
        self.cfg[key] = value
        with open(self.file, "w", encoding="utf-8") as f:
            yaml.dump(data=self.cfg, stream=f, allow_unicode=True)

Config: CFG = CFG("./config/config.yaml")

CLUSTER_ID: str = Config.get("cluster_id", "")
CLUSTER_SECRET: str = Config.get("cluster_secret", "")
MAX_DOWNLOAD: int = Config.get("download_threads", 64)
PORT: int = Config.get("web_port", 8800)
PUBLICPORT: int = Config.get("web_publicport", 8800)
PUBLICHOST: int = Config.get("web_host", "")
BYOC: bool = Config.get("byoc", False)
TIMEOUT: int = Config.get("timeout", 30)
MIN_RATE_TIMESTAMP = 1000
MIN_RATE = 500
REQUEST_BUFFER = 1024 * 8
IO_BUFFER = 1024 * 1024 * 16
ENCODING = "utf-8"
RESPONSE_HEADERS = {
    "Server": "TTB-Network",
}
RESPONSE_DATE = "%a, %d %b %Y %H:%M:%S GMT"
REQUEST_TIME_UNITS = ["ns", "ms", "s", "m", "h"]
BYTES = ["K", "M", "G", "T", "E"] 
status_codes: dict[int, str] = {
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