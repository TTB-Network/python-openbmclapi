from loguru import logger as Logger
from pathlib import Path
import sys
from core.config import Config
from core.i18n import locale

basic_logger_format = "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green><level>[{level}]<yellow>[{name}:{function}:{line}]</yellow>: {message}</level>"
debug_mode = Config.get("advanced.debug")

# 鉴定为屎山
def filter(record):
    if "apscheduler" in record["name"]:
        record["depth"] = 2
    return 1

class LoggingLogger:
    def __init__(self):
        self.log = Logger.opt(depth=1)
        self.log.remove()
        self.log.add(
            sys.stderr,
            format=basic_logger_format,
            level="DEBUG" if debug_mode else "INFO",
            colorize=True,
            filter=filter
        )
        self.cur_handler = None
        self.log.add(
            Path("./logs/{time:YYYY-MM-DD}.log"),
            format=basic_logger_format,
            retention="10 days",
            encoding="utf-8",
            filter=filter
        )
        self.info = self.log.info
        self.debug = self.log.debug
        self.warning = self.log.warning
        self.error = self.log.error
        self.success = self.log.success

    def tinfo(self, key: str, *args, **kwargs):
        self.info(locale.t(key=key, *args, **kwargs))

    def tdebug(self, key: str, *args, **kwargs):
        self.debug(locale.t(key=key, *args, **kwargs))

    def twarning(self, key: str, *args, **kwargs):
        self.warning(locale.t(key=key, *args, **kwargs))

    def terror(self, key: str, *args, **kwargs):
        self.error(locale.t(key=key, *args, **kwargs))

    def tsuccess(self, key: str, *args, **kwargs):
        self.success(locale.t(key=key, *args, **kwargs))


logger = LoggingLogger()
