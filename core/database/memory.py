from collections import defaultdict
from datetime import datetime
from typing import Any
from .abc import DataBase, ClusterCounterInfo


class MemoryDataBase(DataBase):
    def __init__(
        self,
        database_name: str
    ):
        super().__init__(database_name)

        self._clusters_logs = []
        self._clusters_counters: defaultdict[int, defaultdict[str, defaultdict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    async def insert_cluster_info(self, cluster_id: str, type: str, event: str, data: Any | None = None):
        self._clusters_logs.append({
            'cluster_id': cluster_id,
            'type': type,
            'event': event,
            'data': data,
        })

    async def upsert_cluster_counter(self, cluster_id: str, hits: int, bytes: int):
        hour = self.get_hour()
        self._clusters_counters[hour][cluster_id]['hits'] += hits
        self._clusters_counters[hour][cluster_id]['bytes'] += bytes
    
    async def get_cluster_counter(self, cluster_id: str, before_hour: int = 0) -> list[ClusterCounterInfo]:
        res = []
        for h in range(before_hour, self.get_hour() + 1):
            if h not in self._clusters_counters or cluster_id not in self._clusters_counters[h]:
                continue
            res.append(ClusterCounterInfo(
                time=datetime.fromtimestamp(h * 3600),
                hits=self._clusters_counters[h][cluster_id]['hits'],
                bytes=self._clusters_counters[h][cluster_id]['bytes'],
            ))
        return res