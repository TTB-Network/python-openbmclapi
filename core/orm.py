from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column, Session
import time

engine = create_engine("sqlite:///database/data.db")
session = Session(engine)

class Base(DeclarativeBase):
    pass


class HitsInfo(Base):
    __tablename__ = "hits_info"

    hits: Mapped[int] = mapped_column(primary_key=True)
    bytes: Mapped[int]
    time: Mapped[int]


class AgentInfo(Base):
    __tablename__ = "agent_info"

    agent: Mapped[str] = mapped_column(primary_key=True)
    hits: Mapped[int]

def create():
    Base.metadata.create_all(engine)

def write_hits(hits: int, bytes: int):
    session.add_all(HitsInfo(hits=hits, bytes=bytes, time=int(time.time())))
    session.commit()

def write_agent(agent: str, hits: int):
    session.add_all(AgentInfo(agent=agent, hits=hits))