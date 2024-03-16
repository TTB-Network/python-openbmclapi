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

if __name__ == "__main__":
    from core.web import init
    init()
