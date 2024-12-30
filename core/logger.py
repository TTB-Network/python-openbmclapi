import sys
import traceback
from loguru import logger as Logger
from .config import const

LOGGER_FORMAT = "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green> <level>[{level}] <yellow>[{name}:{function}:{line}]</yellow>: {message}</level>"
LOGGER_DIR = "./logs"


_logger = Logger.opt(depth=2)
_logger.remove()
_logger.add(
    f"{LOGGER_DIR}/{{time:YYYY-MM-DD}}.log",
    format=LOGGER_FORMAT,
    retention="90 days",
    encoding="utf-8",
)
_logger.add(
    sys.stderr,
    format=LOGGER_FORMAT,
    level="DEBUG" if const.debug else "INFO",
    colorize=True,
)
from .i18n import locale

class Loglogger:
    def __init__(self, log = _logger) -> None:
        self.log = log
        self.dir = LOGGER_DIR
    def raw_log(self, level, message: str, *values):
        self.log.log(level, message % values)
    def _log_with_args(self, level, *args, **kwargs):
        message = _log(*args) if args else ""
        self.log.log(level, message, **kwargs)
    def info(self, *args, **kwargs):
        self._log_with_args("INFO", *args, **kwargs)
    def error(self, *args, **kwargs):
        self._log_with_args("ERROR", *args, **kwargs)
    def debug(self, *args, **kwargs):
        self._log_with_args("DEBUG", *args, **kwargs)
    def warning(self, *args, **kwargs):
        self._log_with_args("WARNING", *args, **kwargs)
    def success(self, *args, **kwargs):
        self._log_with_args("SUCCESS", *args, **kwargs)
    def traceback(self, *args, **kwargs):
        if args and kwargs:
            self._log_with_args("ERROR", *args, **kwargs)
        self._log_with_args("ERROR", "\n" + traceback.format_exc())

    def tinfo(self, key: str, *args, **kwargs):
        self._log_with_args("INFO", locale.t(
            key, *args, **kwargs
        ))
    def terror(self, key: str, *args, **kwargs):
        self._log_with_args("ERROR", locale.t(
            key, *args, **kwargs
        ))
    def tdebug(self, key: str, *args, **kwargs):
        self._log_with_args("DEBUG", locale.t(
            key, *args, **kwargs
        ))
    def twarning(self, key: str, *args, **kwargs):
        self._log_with_args("WARNING", locale.t(
            key, *args, **kwargs
        ))
    def tsuccess(self, key: str, *args, **kwargs):
        self._log_with_args("SUCCESS", locale.t(
            key, *args, **kwargs
        ))
    def ttraceback(self, key: str, *args, **kwargs):
        if args and kwargs:
            self._log_with_args("ERROR", locale.t(
                key, *args, **kwargs
            ))
        self._log_with_args("ERROR", "\n" + traceback.format_exc())

logger = Loglogger()

def _log(*values):
    data = []
    for v in values:
        try:
            data.append(str(v))
        except:
            data.append(repr(v))
    return " ".join(data)

__all__ = ["logger"]