import inspect
import logging
import sys
import traceback
from loguru import logger as Logger
from .locale import t
from .config import DEBUG

LOGGER_FORMAT = "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green> <level>[{level}] <yellow>[{name}:{function}:{line}]</yellow>: {message}</level>"


_logger = Logger.opt(depth=2)
_logger.remove()
_logger.add(
    "./logs/{time:YYYY-MM-DD}.log",
    format=LOGGER_FORMAT,
    retention="90 days",
    encoding="utf-8",
)
_logger.add(
    sys.stdout,
    format=LOGGER_FORMAT,
    level="DEBUG" if DEBUG else "INFO",
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

    def _log_with_translate_args(self, level: str, key: str, *args, **kwargs):
        self.log.log(level, t(f"{level.lower()}.{key}", *args, **kwargs))
    
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

    def tinfo(self, key: str, *args, **kwargs):
        self._log_with_translate_args("INFO", key, *args, **kwargs)
    def terror(self, key: str,*args, **kwargs):
        self._log_with_translate_args("ERROR", key, *args, **kwargs)
    def tdebug(self, key: str,*args, **kwargs):
        self._log_with_translate_args("DEBUG", key, *args, **kwargs)
    def twarning(self, key: str,*args, **kwargs):
        self._log_with_translate_args("WARNING", key, *args, **kwargs)
    def tsuccess(self, key: str,*args, **kwargs):
        self._log_with_translate_args("SUCCESS", key, *args, **kwargs)
    def ttraceback(self, key: str,*args, **kwargs):
        if args or kwargs:
            self._log_with_translate_args("ERROR", key, *args, **kwargs)
        error = traceback.format_exc()
        self.log.error(error)
    def tdebug_traceback(self, key: str, *args, **kwargs):
        if args or kwargs:
            self._log_with_translate_args("DEBUG", key, *args, **kwargs)
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


# uvicorn

class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = Logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        logger.log.opt(depth=6).log(
            level,
            record.getMessage(),
        )

class DebugHandler(logging.Handler):
    def emit(self, record):
        logger.log.opt(depth=6).log(
            Logger.level('DEBUG').no,
            record.getMessage(),
        )

# 配置拦截处理器
logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG)
logging.getLogger("uvicorn").handlers = [InterceptHandler()]
logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
logging.getLogger("uvicorn.error").handlers = [InterceptHandler()]
#logging.getLogger("engineio.client").handlers = [DebugHandler()]
#logging.getLogger("socketio.client").handlers = [DebugHandler()]




__all__ = ["logger"]