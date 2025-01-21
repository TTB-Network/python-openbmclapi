import sys
import traceback
from loguru import logger as Logger
from .env import env

LOGGER_FORMAT = "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green> <level>[{level}] <yellow>[{name}:{function}:{line}]</yellow>: {message}</level>"



_logger = Logger.opt(depth=2)
_logger.remove()
_logger.add(
    "./logs/{time:YYYY-MM-DD}.log",
    format=LOGGER_FORMAT,
    retention="90 days",
    level=env.get("LOG_LEVEL") or "INFO",
    encoding="utf-8",
)
_logger.add(
    sys.stderr,
    format=LOGGER_FORMAT,
    level=env.get("LOG_LEVEL") or "INFO",
    colorize=True,
)

class Loglogger:
    def __init__(self, log = _logger) -> None:
        self.log = log
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
        if args or kwargs:
            self._log_with_args("ERROR", *args, **kwargs)
        error = traceback.format_exc()
        self.log.error(error)
    def debug_traceback(self, *args, **kwargs):
        if args or kwargs:
            self._log_with_args("DEBUG", *args, **kwargs)
        error = traceback.format_exc()
        self.log.debug(error)

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