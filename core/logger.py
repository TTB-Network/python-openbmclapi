from loguru import logger as Logger
from pathlib import Path
import sys

basic_logger_format = "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green> <yellow>[{name}:{function}:{line}]</yellow> <level>[{level}]: {message}</level>"

class LoggingLogger:
    def __init__(self):
        self.log = Logger
        self.log.remove()
        self.log.add(
            sys.stderr,
            format=basic_logger_format,
            level="INFO",
            colorize=True,
        )
        self.log.add(
            Path("./logs/{time}.log"),
            format=basic_logger_format,
            retention="10 days",
            encoding="utf-8",
        )
        self.info = self.log.info
        self.error = self.log.error
        self.debug = self.log.debug
        self.warn = self.log.warning
        self.exception = self.log.exception

logger = LoggingLogger()
