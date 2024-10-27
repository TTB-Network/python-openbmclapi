from dataclasses import dataclass
import time
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

@dataclass
class StorageStatistics:
    storage: Optional[str] = None
    hits: int = 0
    bytes: int = 0

@dataclass
class Statistics:
    cluster_id: str
    storages: list[StorageStatistics]

engine = create_engine('sqlite:///database.db')
Base = declarative_base()

class ClusterStatisticsTable(Base):
    __tablename__ = 'ClusterStatistics'
    id = Column(Integer, primary_key=True)
    hour = Column(Integer, nullable=False)
    cluster = Column(String, nullable=False)
    hits = Column(String, nullable=False)
    bytes = Column(String, nullable=False)

class StorageStatisticsTable(Base):
    __tablename__ = 'StorageStatistics'
    id = Column(Integer, primary_key=True)
    hour = Column(Integer, nullable=False)
    storage = Column(String, nullable=True)
    hits = Column(String, nullable=False)
    bytes = Column(String, nullable=False)

class Session:
    def __init__(self):
        self.session = sessionmaker(bind=engine)()

    def __del__(self):
        self.session.close()
        del self.session    

    def get_session(self):
        return self.session
    
SESSION = Session()

def add_statistics(data: Statistics):
    session = SESSION.get_session()
    hits, bytes = 0, 0
    hour = get_hour()
    for storage in data.storages:
        if storage.hits == storage.bytes == 0:
            continue
        q = session.query(StorageStatisticsTable).filter_by(hour=hour, storage=storage.storage)
        r = q.first() or StorageStatisticsTable(hour=hour, storage=storage.storage, hits=str(0), bytes=str(0))
        if q.count() == 0:
            session.add(r)
        q.update(
            {
                'hits': str(int(r.hits) + storage.hits), # type: ignore
                'bytes': str(int(r.bytes) + storage.bytes) # type: ignore
            }
        )
        hits += storage.hits
        bytes += storage.bytes
    q = session.query(ClusterStatisticsTable).filter_by(hour=hour, cluster=data.cluster_id)
    r = q.first() or ClusterStatisticsTable(hour=hour, cluster=data.cluster_id, hits=str(0), bytes=str(0))
    if q.count() == 0:
        session.add(r)
    q.update(
        {
            'hits': str(int(r.hits) + hits), # type: ignore
            'bytes': str(int(r.bytes) + bytes) # type: ignore
        }
    )
    session.commit()
    


def get_hour():
    return int(time.time() // 3600)

Base.metadata.create_all(engine)