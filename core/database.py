from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Optional
import pyzstd
from sqlalchemy import create_engine, Column, Integer, String, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from core import logger, scheduler, utils

@dataclass
class StorageStatistics:
    storage: Optional[str] = None
    hits: int = 0
    bytes: int = 0

@dataclass
class Statistics:
    cluster_id: str
    storages: list[StorageStatistics]

@dataclass
class FileStatisticsKey:
    hour: int
    cluster_id: str
    storage_id: Optional[str]

    def __hash__(self):
        return hash((self.hour, self.cluster_id, self.storage_id))

@dataclass
class FileStatistics:
    hits: int = 0
    bytes: int = 0

@dataclass
class ResponseStatistics:
    success: int = 0
    not_found: int = 0
    forbidden: int = 0
    error: int = 0
    redirect: int = 0
    ip_tables: defaultdict[str, int] = field(default_factory=lambda: defaultdict(int))



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

class ResponseTable(Base):
    __tablename__ = 'Responses'
    id = Column(Integer, primary_key=True)
    hour = Column(Integer, nullable=False)
    success = Column(String, nullable=False)
    forbidden = Column(String, nullable=False)
    not_found = Column(String, nullable=False)
    error = Column(String, nullable=False)
    redirect = Column(String, nullable=False)
    ip_tables = Column(LargeBinary, nullable=False)

class StatusType(Enum):
    SUCCESS = "success"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    ERROR = "error"
    REDIRECT = "redirect"

class Session:
    def __init__(self):
        self.session = sessionmaker(bind=engine)()

    def __del__(self):
        self.session.close()
        del self.session    

    def get_session(self):
        return self.session
    
SESSION = Session()
FILE_CACHE: defaultdict[FileStatisticsKey, FileStatistics] = defaultdict(lambda: FileStatistics())
RESPONSE_CACHE: defaultdict[int, ResponseStatistics] = defaultdict(lambda: ResponseStatistics())

@DeprecationWarning
def add_statistics(data: Statistics):
    return
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

def add_file(cluster: str, storage: Optional[str], bytes: int):
    global FILE_CACHE
    key = FileStatisticsKey(get_hour(), cluster, storage)
    FILE_CACHE[key].bytes += bytes
    FILE_CACHE[key].hits += 1

def add_response(ip: str, type: StatusType):
    global RESPONSE_CACHE
    hour = get_hour()
    RESPONSE_CACHE[hour].ip_tables[ip] += 1
    setattr(RESPONSE_CACHE[hour], type.value, getattr(RESPONSE_CACHE[hour], type.value) + 1)

def get_hour():
    return int(time.time() // 3600)

def _commit_storage(hour: int, storage: Optional[str], hits: int, bytes: int):
    if hits == bytes == 0:
        return False
    session = SESSION.get_session()
    q = session.query(StorageStatisticsTable).filter_by(hour=hour, storage=storage)
    r = q.first() or StorageStatisticsTable(hour=hour, storage=storage, hits=str(0), bytes=str(0))
    if q.count() == 0:
        session.add(r)
    q.update(
        {
            'hits': str(int(r.hits) + hits), # type: ignore
            'bytes': str(int(r.bytes) + bytes) # type: ignore
        }
    )
    return True

def _commit_cluster(hour: int, cluster: str, hits: int, bytes: int):
    if hits == bytes == 0:
        return False
    session = SESSION.get_session()
    q = session.query(ClusterStatisticsTable).filter_by(hour=hour, cluster=cluster)
    r = q.first() or ClusterStatisticsTable(hour=hour, cluster=cluster, hits=str(0), bytes=str(0))
    if q.count() == 0:
        session.add(r)
    q.update(
        {
            'hits': str(int(r.hits) + hits), # type: ignore
            'bytes': str(int(r.bytes) + bytes) # type: ignore
        }
    )
    return True

def _commit_response(hour: int, ip_tables: defaultdict[str, int], success: int = 0, forbidden: int = 0, redirect: int = 0, not_found: int = 0, error: int = 0):
    if ip_tables == {}:
        return False
    session = SESSION.get_session()
    q = session.query(ResponseTable).filter_by(hour=hour)
    r = q.first() or ResponseTable(hour=hour, ip_tables=b'', success=str(0), forbidden=str(0), redirect=str(0), not_found=str(0), error=str(0))
    if q.count() == 0:
        session.add(r)
    origin_ip_tables: defaultdict[str, int] = defaultdict(lambda: 0)
    ip_tables_data: bytes = r.ip_tables # type: ignore
    if ip_tables_data:
        try:
            input = utils.DataInputStream(pyzstd.decompress(ip_tables_data))
            for _ in range(input.read_long()):
                ip = input.read_string()
                count = input.read_long()
                origin_ip_tables[ip] = count
        except:
            logger.ttraceback("database.error.unable.to.decompress.ip.tables", ip_tables_data)
            origin_ip_tables.clear()
    for ip, count in ip_tables.items():
        origin_ip_tables[ip] += count
    output = utils.DataOutputStream()
    output.write_long(len(origin_ip_tables))
    for ip, count in origin_ip_tables.items():
        output.write_string(ip)
        output.write_long(count)
    q.update(
        {
            'ip_tables': pyzstd.compress(output.getvalue()), # type: ignore
            'success': str(int(r.success) + success), # type: ignore
            'forbidden': str(int(r.forbidden) + forbidden), # type: ignore
            'redirect': str(int(r.redirect) + redirect), # type: ignore
            'not_found': str(int(r.not_found) + not_found), # type: ignore
            'error': str(int(r.error) + error) # type: ignore
        }
    )
    return True

def commit():
    global FILE_CACHE
    total_hits = 0
    total_bytes = 0
    total_storages = 0
    cache = FILE_CACHE.copy()
    session = SESSION.get_session()
    clusters: defaultdict[tuple[int, str], FileStatistics] = defaultdict(lambda: FileStatistics(0, 0))
    for key, value in FILE_CACHE.items():
        hour = key.hour
        cluster = key.cluster_id
        storage = key.storage_id
        hits = value.hits
        bytes = value.bytes
        if _commit_storage(hour, storage, hits, bytes):
            total_hits += hits
            total_bytes += bytes
            total_storages += 1
            clusters[(hour, cluster)].hits += hits
            clusters[(hour, cluster)].bytes += bytes
    for cluster, value in clusters.items():
        _commit_cluster(cluster[0], cluster[1], value.hits, value.bytes)

    for hour, value in RESPONSE_CACHE.items():
        _commit_response(hour, value.ip_tables, value.success, value.forbidden, value.redirect, value.not_found, value.error)


    logger.success(f'Committing {total_hits} hits and {total_bytes} bytes to database. {total_storages} storages updated')
    
    session.commit()
    old_keys = []
    for key, value in cache.items():
        FILE_CACHE[key].hits -= value.hits
        FILE_CACHE[key].bytes -= value.bytes
        if FILE_CACHE[key].hits == FILE_CACHE[key].bytes == 0:
            old_keys.append(key)
    for key in old_keys:
        del FILE_CACHE[key]
    
    old_keys.clear()

    for hour, value in RESPONSE_CACHE.items():
        RESPONSE_CACHE[hour].success -= value.success
        RESPONSE_CACHE[hour].forbidden -= value.forbidden
        RESPONSE_CACHE[hour].redirect -= value.redirect
        RESPONSE_CACHE[hour].not_found -= value.not_found
        RESPONSE_CACHE[hour].error -= value.error
        ip_hits = 0
        for ip, hits in value.ip_tables.items():
            RESPONSE_CACHE[hour].ip_tables[ip] -= hits
            ip_hits += RESPONSE_CACHE[hour].ip_tables[ip]
        if RESPONSE_CACHE[hour].success == RESPONSE_CACHE[hour].forbidden == RESPONSE_CACHE[hour].redirect == RESPONSE_CACHE[hour].not_found == RESPONSE_CACHE[hour].error == ip_hits == 0:
            old_keys.append(hour)
    for key in old_keys:
        del RESPONSE_CACHE[key]

async def init():
    Base.metadata.create_all(engine)
    scheduler.run_repeat_later(commit, 5, 10)

async def unload():
    commit()