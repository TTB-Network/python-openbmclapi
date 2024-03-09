from loguru import logger
from pathlib import Path

logger.add(Path("./logs/{time}.log"), rotation="3 hours")
