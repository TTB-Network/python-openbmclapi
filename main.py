from datetime import datetime
import os
import sys
import time

cur = time.time()
os.environ["UTC"] = str(
    int(
        (datetime.fromtimestamp(cur) - datetime.fromtimestamp(cur)).total_seconds()
        / 3600
    )
)
os.environ["STARTUP"] = str(
    cur
)
os.environ["ASYNCIO_STARTUP"] = str(
    0
)

if __name__ == "__main__":
    if sys.version_info <= (3, 9):
        print(f"Not support version: {sys.version}. Please update python to 3.10+")
        exit(-1)
    import core

    core.init()
