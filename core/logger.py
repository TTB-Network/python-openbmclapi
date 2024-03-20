from loguru import logger as Logger
from pathlib import Path
import sys

basic_logger_format = "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green> <level>[{level}] {message}</level>"

def log(*values, func):
    data = []
    for v in values:
        try:
            data.append(str(v))
        except:
            data.append(repr(v))
    msg = " ".join(data)
    func(msg)
class LoggingLogger:
    def __init__(self):
        self.log = Logger
        self.log.remove()
        self.log.add(
            sys.stderr,
            format=basic_logger_format,
            level="DEBUG",
            colorize=True,
        )
        self.log.add(
            Path("./logs/{time}.log"),
            format=basic_logger_format,
            retention="10 days",
            encoding="utf-8",
        )
        self.info       = lambda *x: log(*x, func=self.log.info)
        self.error      = lambda *x: log(*x, func=self.log.error)
        self.debug      = lambda *x: log(*x, func=self.log.debug)
        self.warn       = lambda *x: log(*x, func=self.log.warning)
        self.exception  = lambda *x: log(*x, func=self.log.exception)

logger = LoggingLogger()