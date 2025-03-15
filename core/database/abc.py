import abc
from dataclasses import dataclass
import datetime
from pathlib import Path
import time
from typing import Any, Optional

ROOT = Path(__file__).parent.parent.parent / 'database'
ROOT.mkdir(parents=True, exist_ok=True)

@dataclass
class ClusterCounterInfo:
    time: datetime.datetime
    hits: int
    bytes: int

class DataBase(
    metaclass=abc.ABCMeta
):
    """Abstract class for database"""

    def __init__(
        self,
        database_name: str
    ):
        self.database_name = database_name

    @abc.abstractmethod
    async def insert_cluster_info(
        self,
        cluster_id: str,
        type: str,
        event: str,
        data: Optional[Any] = None
    ):
        """Insert cluster info into database"""
        pass

    @abc.abstractmethod
    async def upsert_cluster_counter(
        self,
        cluster_id: str,
        hits: int,
        bytes: int
    ):
        """Upsert cluster counter into database"""
        pass

    @abc.abstractmethod
    async def get_cluster_counter(
        self,
        cluster_id: str,
        before_hour: int = 0
    ) -> list[ClusterCounterInfo]:
        """Get cluster counter from database"""
        pass


    def get_hour(self) -> int:
        # Asia/Shanghai
        # use timestamp
        return int(time.time() // 3600)
    
