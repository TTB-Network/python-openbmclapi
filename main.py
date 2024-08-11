import core
import asyncio
from core.logger import logger

if __name__ == '__main__':
    logger.tinfo('main.info.start')
    asyncio.run(core.init())