from datetime import datetime
from typing import Any, Optional
import motor.motor_asyncio as motor
import urllib.parse as urlparse

from core.database.abc import ClusterCounterInfo 

from .abc import DataBase

class MongoDB(DataBase):
    def __init__(
        self, 
        database_name: str,
        host: str,
        port: int,
        **kwargs
    ):
        super().__init__(
            database_name=database_name
        )

        user = ""
        if "username" in kwargs and "password":
            user = f":".join((
                urlparse.quote(x) for x in (
                    kwargs["username"],
                    kwargs["password"]
                )
            )) + "@"
            

        self.connection = motor.AsyncIOMotorClient(f"mongodb://{user}{host}:{port}")

        self.db = self.connection.get_database(f"{database_name}")
    
    async def insert_cluster_info(self, cluster_id: str, type: str, event: str, data: Optional[Any] = None):
        await self.db["cluster_logs"].insert_one({
            "cluster_id": cluster_id,
            "type": type,
            "event": event,
            "data": data
        })

    async def upsert_cluster_counter(self, cluster_id: str, hits: int, bytes: int):
        # add
        await self.db["cluster_counters"].update_one(
            {
                "cluster_id": cluster_id,
                "hour": self.get_hour()
            },
            {
                "$inc": {
                    "hits": hits,
                    "bytes": bytes
                }
            },
            upsert=True
        )

    async def get_cluster_counter(self, cluster_id: str, before_hour: int = 0) -> list[ClusterCounterInfo]:
        res = []
        async for doc in self.db.get_collection("cluster_counters").find({
            "cluster_id": cluster_id,
            "hour": {"$gte": before_hour, "$lt": self.get_hour()}
        }):
            res.append(ClusterCounterInfo(
                time=datetime.fromtimestamp(doc["hour"] * 3600),
                hits=doc["hits"],
                bytes=doc["bytes"]
            ))
        return res


