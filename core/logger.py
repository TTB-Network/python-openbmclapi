from loguru import logger as Logger
from pathlib import Path
import sys

basic_logger_format = "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green> <level>[{level}] <yellow>[{name}:{function}:{line}]</yellow>: {message}</level>"


def log(*values):  
    data = []  
    for v in values:  
        try:  
            data.append(str(v))  
        except:  
            data.append(repr(v))  
    return " ".join(data)  
  
  
class LoggingLogger:  
    def __init__(self):  
        self.log = Logger.opt(depth=2)
        self.log.remove()  
        self.log.add(  
            sys.stderr,  
            format=basic_logger_format,  
            level="DEBUG",  
            colorize=True,  
        )  
        self.log.add(  
            Path("./logs/{time:YYYY-MM-DD}.log"),  
            format=basic_logger_format,  
            retention="10 days",  
            encoding="utf-8",  
        )  
  
    def _log_with_args(self, level, *args, **kwargs):  
        message = log(*args) if args else ""  
        self.log.log(level, message, **kwargs)  
  
    def info(self, *args, **kwargs):  
        self._log_with_args("INFO", *args, **kwargs)  
  
    def error(self, *args, **kwargs):  
        self._log_with_args("ERROR", *args, **kwargs)  
  
    def debug(self, *args, **kwargs):  
        self._log_with_args("DEBUG", *args, **kwargs)  
  
    def warn(self, *args, **kwargs):  
        self._log_with_args("WARNING", *args, **kwargs)  
  
    def exception(self, *args, **kwargs):  
        self._log_with_args("EXCEPTION", *args, **kwargs) 


logger = LoggingLogger()
