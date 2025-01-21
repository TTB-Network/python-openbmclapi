from .env import env
import motor.motor_asyncio

import urllib.parse as urlparse

mongodb_username = urlparse.quote(env.get('MONGODB_USERNAME') or "")
mongodb_password = urlparse.quote(env.get('MONGODB_PASSWORD') or "")
mongodb_host = env.get('MONGODB_HOST') or "localhost"
mongodb_port = env.get('MONGODB_PORT') or "27017"
mongodb_database_prefix = env.get('MONGODB_DATABASE_PREFIX') or "MMCM_"

client = motor.motor_asyncio.AsyncIOMotorClient(f"mongodb://{mongodb_username}:{mongodb_password}@{mongodb_host}:{mongodb_port}")

def get_database(
    name: str,
) -> motor.motor_asyncio.AsyncIOMotorDatabase:
    return client.get_database(f"{mongodb_database_prefix}{name}")
    

__all__ = ['get_database']