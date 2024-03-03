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
CLUSTER_ID = Config.get("cluster.id", None)
CLUSTER_SECRET = Config.get("cluster.secret", None)
USER_AGENT = "openbmclapi-cluster"
MAX_DOWNLOAD = Config.getInteger("download.threads", 64)
ssl = Config.getBoolean("web.ssl", False)
port = Config.getInteger("web.port", 8800)
publicPort = Config.getInteger("web.publicport", 8800)
publicHost = Config.get("web.host", "")
SKIP_SIGN = Config.getBoolean("web.skipsign", True)