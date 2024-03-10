from datetime import datetime
import os
import time
cur = time.time()
os.environ["UTC"] = str(int((datetime.fromtimestamp(cur) - datetime.utcfromtimestamp(cur)).total_seconds() / 3600))

if __name__ == "__main__":
    import web
    web.init()