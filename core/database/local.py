import datetime
from typing import Any, Optional

from . import abc

try:
    import sqlite3 as sqlite
except:
    try:
        import pysqlite3 as sqlite # type: ignore
    except:
        print("Error: sqlite3 or pysqlite3 not found")
        exit(1)

class SqliteDB(abc.DataBase):
    def __init__(
        self,
        database_name: str
    ):
        super().__init__(database_name)

        self.clusters = sqlite.connect(
            abc.ROOT / f'{self.database_name}_clusters.db'
        )

        self.clusters.execute('create table if not exists logs (timestamp text, cluster_id text, type text, event text, data text)')
        # hits, bytes unsigned big integer
        self.clusters.execute('create table if not exists counters (hour text, cluster_id text, hits unsigned big integer, bytes unsigned big integer, primary key (hour, cluster_id))')
        self.clusters.commit()
    
    async def insert_cluster_info(self, cluster_id: str, type: str, event: str, data: Optional[Any] = None):
        self.clusters.execute(
            'insert into logs values (?, ?, ?, ?, ?)',
            (datetime.datetime.now().isoformat(), cluster_id, type, event, data)
        )
        self.clusters.commit()
    
    async def upsert_cluster_counter(self, cluster_id: str, hits: int, bytes: int):
        hour = self.get_hour()
        self.clusters.execute(
            'insert into counters values (?, ?, ?, ?) on conflict (hour, cluster_id) do update set hits = hits + ?, bytes = bytes + ?',
            (hour, cluster_id, hits, bytes, hits, bytes)
        )
        self.clusters.commit()

    async def get_cluster_counter(self, cluster_id: str, before_hour: int = 0) -> list[abc.ClusterCounterInfo]:
        return [
            abc.ClusterCounterInfo(
                time=datetime.datetime.fromtimestamp(row[0] * 3600),
                hits=row[1],
                bytes=row[2]
            ) for row in self.clusters.execute(
                'select hour, hits, bytes from counters where cluster_id = ? and hour >= ? and hour <= ?',
                (cluster_id, before_hour, self.get_hour())
            )
        ]

    def __del__(self):
        self.clusters.close()