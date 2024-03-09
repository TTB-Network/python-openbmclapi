from pathlib import Path


class Property:  
    def __init__(self, config: str, exists_ok: bool = True) -> None:  
        self.file = Path(config)  
        self.properties = {}  
        if self.file.exists():  
            self.parse_file()  
        self.exists_ok = exists_ok
  
    def parse_file(self):  
        with open(self.file, "r", encoding="utf-8") as f:
            for line in f.readlines():  
                line = line.strip()  
                if not line or line.startswith('#'):  
                    continue
                key, value = line.split('=', 1)  
                value = value.strip('"')  
                self.properties[key] = value  
    def set(self, key, value):
        self.properties[key] = str(value)

    def get(self, key, default=None):  
        val = self.properties.get(key, None)  
        if not self.exists_ok and val is None:
            self.set(key, default or "")
            self.save()
        return val or str(default)
    def getBoolean(self, key, def_: bool = False):
        val = self.get(key, def_)
        return val.lower() in ("true", "1", "t", "yes", "y")
    def getInteger(self, key, def_: int = 0):
        val = self.get(key, def_)
        return int(val) if val.isnumeric() else def_
    def __getitem__(self, key):
        return self.properties.get(key)  
    def __setitem__(self, key, value):
        self.set(key, value)
    
    def save(self):
        sorted_dict = sorted(self.properties.items())  
        self.file.parent.mkdir(exist_ok=True, parents=True)
        with open(self.file, 'w', encoding="utf-8") as file:  
            for key, value in sorted_dict:  
                if "\n" in value:
                    value = f'"{value}"'
                file.write(f"{key}={value}\n")

Config: Property = Property("./config/config.properties", False)

CLUSTER_ID = Config.get("cluster.id", None) or ""
CLUSTER_SECRET = Config.get("cluster.secret", None) or ""
MAX_DOWNLOAD = Config.getInteger("download.threads", 64)
PORT = Config.getInteger("web.port", 8800)
PUBLICPORT = Config.getInteger("web.publicport", 8800)
PUBLICHOST = Config.get("web.host", "")
BYOC = False
TIMEOUT = 30
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