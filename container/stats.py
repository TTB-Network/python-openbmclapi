
from dataclasses import dataclass
from pathlib import Path

from utils import FileDataInputStream, FileDataOutputStream
from timer import Timer # type: ignore


@dataclass
class Counters:
    hit: int = 0
    bytes: int = 0

counter = Counters()
cache: Path = Path("./cache")
cache.mkdir(exist_ok=True, parents=True)
def write():
    with open("./cache/stats_count.bin", "wb") as w:
        f = FileDataOutputStream(w)
        f.writeVarInt(counter.hit)
        f.writeVarInt(counter.bytes)

def read():
    if Path("./cache/stats_count.bin").exists():
        with open("stats_count.bin", "rb") as r:
            f = FileDataInputStream(r)
            counter.hit += f.readVarInt()
            counter.bytes += f.readVarInt()

Timer.repeat(write, (), 0.01, 0.1)
