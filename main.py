from datetime import datetime
import os
import sys
import time
from core.i18n import locale

cur = time.time()
os.environ["UTC"] = str(
    int(
        (datetime.fromtimestamp(cur) - datetime.fromtimestamp(cur)).total_seconds()
        / 3600
    )
)
os.environ["STARTUP"] = str(cur)
os.environ["ASYNCIO_STARTUP"] = str(0)
os.environ["MONOTONIC"] = str(time.monotonic())

if __name__ == "__main__":
    if sys.version_info <= (3, 9):
        print(locale.t("main.unsupported_version"))
        exit(-1)
    import core

    core.init()
