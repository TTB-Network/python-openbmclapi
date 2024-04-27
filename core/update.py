import asyncio
import os
import aiohttp
from tqdm import tqdm

from core import dashboard, logger, scheduler
from core.const import AUTO_DOWNLOAD_RELEASE, IO_BUFFER, VERSION
from core.timings import logTqdm, logTqdmType


github_api = "https://api.github.com"
download_url = ""


async def check_update():
    global fetched_version, download_url
    fetched_version = "Unknown"
    async with aiohttp.ClientSession(base_url=github_api) as session:
        logger.tinfo("cluster.info.check_update.checking")
        try:
            async with session.get(
                "/repos/TTB-Network/python-openbmclapi/releases/latest",
                timeout=5
            ) as req:
                req.raise_for_status()
                data = await req.json()
                fetched_version = data["tag_name"]
                download_url = data["zipball_url"]
            if fetched_version != VERSION:
                logger.tsuccess(
                    "cluster.success.check_update.new_version",
                    latest=fetched_version,
                )
                await dashboard.trigger("version")
                if AUTO_DOWNLOAD_RELEASE:
                    scheduler.delay(download)
            else:
                logger.tinfo("cluster.info.check_update.already_up_to_date")
        except aiohttp.ClientError as e:
            logger.terror("cluster.error.check_update.failed", e=e)
        except asyncio.CancelledError:
            await session.close()
            return


async def download():
    global download_url
    if not download_url:
        return
    if not os.path.exists("./releases"):
        os.mkdir("./releases")
    filename = f"{fetched_version}.zip"
    if os.path.exists(f"./releases/{filename}"):
        return
    async with aiohttp.ClientSession() as session:
        async with session.get(download_url) as resp:
            length = int(resp.headers.get("Content-Length") or 0)
            filename = f"{fetched_version}.zip"
            with tqdm(total=length, desc="Download Release", unit="b", unit_divisor=1024, unit_scale=True) as pbar, logTqdm(pbar, logTqdmType.BYTES), open(f"./releases/{filename}", "wb") as w:
                while (data := await resp.content.read(IO_BUFFER)):
                    pbar.update(len(data))
                    w.write(data)
def init():
    scheduler.repeat(check_update, interval=3600)