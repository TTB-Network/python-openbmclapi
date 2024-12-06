from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from typing import Optional
import pyzstd
from sqlalchemy import create_engine, Column, Integer, String, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.decl_api import DeclarativeMeta

from core import logger, scheduler, storages, utils

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
    partial: int = 0
    ip_tables: defaultdict[str, int] = field(default_factory=lambda: defaultdict(int))
    user_agents: defaultdict[str, int] = field(default_factory=lambda: defaultdict(int))



engine = create_engine('sqlite:///database.db')
Base: DeclarativeMeta = declarative_base()

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
    partial = Column(String, nullable=False)
    forbidden = Column(String, nullable=False)
    not_found = Column(String, nullable=False)
    error = Column(String, nullable=False)
    redirect = Column(String, nullable=False)
    ip_tables = Column(LargeBinary, nullable=False)
    user_agents = Column(LargeBinary, nullable=False)

class StorageUniqueIDTable(Base):
    __tablename__ = 'StorageUniqueID'
    id = Column(Integer, primary_key=True)
    unique_id = Column(String, nullable=False)
    data = Column(String, nullable=False)

class StatusType(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
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

def add_file(cluster: str, storage: Optional[str], bytes: int):
    global FILE_CACHE
    key = FileStatisticsKey(get_hour(), cluster, storage)
    FILE_CACHE[key].bytes += bytes
    FILE_CACHE[key].hits += 1

def add_response(ip: str, type: StatusType, user_agent: str):
    global RESPONSE_CACHE
    hour = get_hour()
    RESPONSE_CACHE[hour].ip_tables[ip] += 1
    RESPONSE_CACHE[hour].user_agents[user_agent] += 1
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

def _commit_response(hour: int, ip_tables: defaultdict[str, int], user_agents: defaultdict[str, int], success: int = 0, forbidden: int = 0, redirect: int = 0, not_found: int = 0, error: int = 0, partial: int = 0):
    if ip_tables == {}:
        return False
    session = SESSION.get_session()
    q = session.query(ResponseTable).filter_by(hour=hour)
    r = q.first() or ResponseTable(hour=hour, ip_tables=b'', user_agents=b'', success=str(0), forbidden=str(0), redirect=str(0), not_found=str(0), error=str(0), partial=str(0))
    if q.count() == 0:
        session.add(r)
    origin_ip_tables: defaultdict[str, int] = decompress(r.ip_tables) # type: ignore
    origin_user_agents: defaultdict[str, int] = decompress(r.user_agents) # type: ignore
    for ip, count in ip_tables.items():
        origin_ip_tables[ip] += count
    
    for user_agent, count in user_agents.items():
        origin_user_agents[user_agent] += count
    q.update(
        {
            'ip_tables': compress(origin_ip_tables), # type: ignore
            'user_agents': compress(origin_user_agents), # type: ignore
            'success': str(int(r.success) + success), # type: ignore
            'forbidden': str(int(r.forbidden) + forbidden), # type: ignore
            'redirect': str(int(r.redirect) + redirect), # type: ignore
            'not_found': str(int(r.not_found) + not_found), # type: ignore
            'error': str(int(r.error) + error), # type: ignore
            'partial': str(int(r.partial) + partial) # type: ignore
        }
    )
    return True

def compress(data: defaultdict[str, int]) -> bytes:
    output = utils.DataOutputStream()
    output.write_long(len(data))
    for key, val in data.items():
        output.write_string(key)
        output.write_long(val)
    return pyzstd.compress(output.getvalue())

def decompress(data: bytes) -> defaultdict[str, int]:
    if not data:
        return defaultdict(lambda: 0)
    try:
        input = utils.DataInputStream(pyzstd.decompress(data))
        result = defaultdict(lambda: 0)
        for _ in range(input.read_long()):
            key = input.read_string()
            val = input.read_long()
            result[key] += val
        return result
    except:
        logger.ttraceback("database.error.unable.to.decompress", data=data)
        return defaultdict(lambda: 0)


def commit():
    try:
        global FILE_CACHE
        total_hits = 0
        total_bytes = 0
        total_storages = 0
        cache = FILE_CACHE.copy()
        response_cache = RESPONSE_CACHE.copy()
        session = SESSION.get_session()
        clusters: defaultdict[tuple[int, str], FileStatistics] = defaultdict(lambda: FileStatistics(0, 0))
        for key, value in cache.items():
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

        for hour, value in response_cache.items():
            _commit_response(hour, value.ip_tables, value.user_agents, value.success, value.forbidden, value.redirect, value.not_found, value.error, value.partial)

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

        for hour, value in response_cache.items():
            RESPONSE_CACHE[hour].success -= value.success
            RESPONSE_CACHE[hour].forbidden -= value.forbidden
            RESPONSE_CACHE[hour].redirect -= value.redirect
            RESPONSE_CACHE[hour].not_found -= value.not_found
            RESPONSE_CACHE[hour].error -= value.error
            ip_hits = 0
            user_agent_hits = 0
            for ip, hits in value.ip_tables.items():
                RESPONSE_CACHE[hour].ip_tables[ip] -= hits
                ip_hits += RESPONSE_CACHE[hour].ip_tables[ip]
            for user_agent, hits in value.user_agents.items():
                RESPONSE_CACHE[hour].user_agents[user_agent] -= hits
                user_agent_hits += RESPONSE_CACHE[hour].user_agents[user_agent]
            if RESPONSE_CACHE[hour].success == RESPONSE_CACHE[hour].forbidden == RESPONSE_CACHE[hour].redirect == RESPONSE_CACHE[hour].not_found == RESPONSE_CACHE[hour].error == ip_hits == user_agent_hits == 0:
                old_keys.append(hour)
        for key in old_keys:
            del RESPONSE_CACHE[key]
    except:
        logger.terror("database.error.write")

def init_storages_key(*storage: storages.iStorage):
    session = SESSION.get_session()
    for s in storage:
        data = {
            "type": s.type,
            "path": s.path,
        }
        if isinstance(s, storages.AlistStorage):
            data["url"] = s.url
        content = json.dumps(data, separators=(',', ':'))
        
        q = session.query(StorageUniqueIDTable).filter(StorageUniqueIDTable.unique_id == s.unique_id)
        r = q.first() or StorageUniqueIDTable(
            unique_id = s.unique_id,
            data = content
        )
        if q.count() == 0:
            session.add(r)
    session.commit()


async def init():
    Base.metadata.create_all(engine)
    scheduler.run_repeat_later(commit, 5, 10)

async def unload():
    commit()