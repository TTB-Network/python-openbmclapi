from datetime import datetime
import os
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
    import core

    core.init()
