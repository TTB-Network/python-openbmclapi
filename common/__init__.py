from .logger import logger
from .env import env
from .database import get_database
from .timings import Timings
from . import units
from .telegram import bot as telegram_bot


async def shutdown():
    await telegram_bot.wait_closed()