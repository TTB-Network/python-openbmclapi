from enum import Enum
import inspect
import io
import sys
import time
STDOUT = sys.stdout
class Stdout(io.StringIO):
    def write(self, __s: str) -> int:
        return STDOUT.write(__s)
    def flush(self) -> None:
        return STDOUT.flush()
    def seek(self, __cookie: int, __whence: int = 0) -> int:
        return STDOUT.seek(__cookie, __whence)
sys.stdout = Stdout()

class PrintStdout(io.StringIO):
    def write(self, __s: str) -> int:
        info(__s.lstrip("\r"), flush=True)
        return len(__s)
PRINTSTDOUT = PrintStdout()

class Level(Enum):  
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
LevelColors: dict[Level, str] = {
    Level.DEBUG: "reset",
    Level.INFO: "green",
    Level.WARNING: "yellow",
    Level.ERROR: "red"
}

def logger(*values, level: Level, flush: bool = False, stack: list[inspect.FrameInfo]):
    stackname = stack[1].function + str(stack[1].lineno)
    print(*(f"<<<flush:{flush},time:{time.time()},stack:{stackname},color:{LevelColors.get(level, 'reset')}>>>[{level.name.upper()}]", *values))

def info(*values, flush: bool = False):
    return logger(*values, flush=flush, level=Level.INFO, stack=inspect.stack())

def error(*values, flush: bool = False):
    return logger(*values, flush=flush, level=Level.ERROR, stack=inspect.stack())

def warning(*values, flush: bool = False):
    return logger(*values, flush=flush, level=Level.WARNING, stack=inspect.stack())

def debug(*values, flush: bool = False):
    return logger(*values, flush=flush, level=Level.DEBUG, stack=inspect.stack())