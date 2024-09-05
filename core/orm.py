from sqlalchemy import create_engine, select
from sqlalchemy.orm import Mapped, mapped_column, Session, DeclarativeBase
from datetime import timedelta, datetime
from calendar import monthrange
from typing import List, Dict
import time
import re

engine = create_engine("sqlite:///database/data.db")
session = Session(engine)


class Base(DeclarativeBase):
    pass


class HitsInfo(Base):
    __tablename__ = "hits_info"

    time: Mapped[int] = mapped_column(primary_key=True)
    hits: Mapped[int]
    bytes: Mapped[int]


class AgentInfo(Base):
    __tablename__ = "agent_info"

    agent: Mapped[str] = mapped_column(primary_key=True)
    hits: Mapped[int]


def create() -> None:
    Base.metadata.create_all(engine)


def writeHits(hits: int, bytes: int) -> None:
    if hits == 0 and bytes == 0:
        return
    session.add(HitsInfo(hits=hits, bytes=bytes, time=int(time.time())))
    try:
        session.commit()
    except Exception:
        session.rollback()


def writeAgent(agent: str, hits: int) -> None:
    agent = re.match(r"^(.*?)/", agent).group(1)
    if agent not in ["bmclapi-ctrl", "bmclapi-warden"]:
        agent_info = session.get(AgentInfo, agent)
        if agent_info:
            agent_info.hits += hits
        else:
            session.add(AgentInfo(agent=agent, hits=hits))

        try:
            session.commit()
        except Exception:
            session.rollback()


def getHourlyHits() -> Dict[str, List[Dict[str, int]]]:
    def fetchData(base_time: datetime) -> List[Dict[str, int]]:
        timestamps = [
            int((base_time + timedelta(hours=i)).timestamp()) for i in range(24)
        ] + [int((base_time.replace(hour=1) + timedelta(days=1)).timestamp())]

        return [
            {
                "hits": sum(item.hits for item in query) if query else 0,
                "bytes": sum(item.bytes for item in query) if query else 0,
            }
            for i in range(24)
            for query in [
                session.execute(
                    select(HitsInfo).where(
                        HitsInfo.time >= timestamps[i],
                        HitsInfo.time < timestamps[i + 1],
                    )
                )
                .scalars()
                .all()
            ]
        ]

    current = datetime.now().replace(hour=1, minute=0, second=0, microsecond=0)
    previous = current - timedelta(days=1)
    return {"stats": fetchData(current), "prevStats": fetchData(previous)}


def getDailyHits() -> Dict[str, List[Dict[str, int]]]:
    def fetchData(year: int, month: int, total_days: int) -> List[Dict[str, int]]:
        return [
            {
                "hits": sum(item.hits for item in query),
                "bytes": sum(item.bytes for item in query),
            }
            for day in range(1, total_days + 1)
            for query in [
                session.execute(
                    select(HitsInfo).where(
                        HitsInfo.time >= int(datetime(year, month, day).timestamp()),
                        HitsInfo.time
                        < int(
                            (datetime(year, month, day) + timedelta(days=1)).timestamp()
                        ),
                    )
                )
                .scalars()
                .all()
            ]
        ]

    now = datetime.now()
    current_year, current_month = now.year, now.month
    previous_year, previous_month = (
        (current_year - 1, 12)
        if current_month == 1
        else (current_year, current_month - 1)
    )

    return {
        "stats": fetchData(
            current_year, current_month, monthrange(current_year, current_month)[1]
        ),
        "prevStats": fetchData(
            previous_year, previous_month, monthrange(previous_year, previous_month)[1]
        ),
    }


def getMonthlyHits() -> Dict[str, List[Dict[str, int]]]:
    def fetchData(year: int) -> List[Dict[str, int]]:
        return [
            {
                "hits": sum(item.hits for item in query),
                "bytes": sum(item.bytes for item in query),
            }
            for month in range(1, 13)
            for query in [
                session.execute(
                    select(HitsInfo).where(
                        HitsInfo.time >= int(datetime(year, month, 1).timestamp()),
                        HitsInfo.time
                        < int(
                            datetime(
                                year if month < 12 else year + 1,
                                month + 1 if month < 12 else 1,
                                1,
                            ).timestamp()
                        ),
                    )
                )
                .scalars()
                .all()
            ]
        ]

    now = datetime.now()
    current_year = now.year
    previous_year = current_year - 1

    return {"stats": fetchData(current_year), "prevStats": fetchData(previous_year)}


def getAgentInfo() -> Dict[str, int]:
    agents_info = session.execute(select(AgentInfo)).scalars().all()

    return {agent.agent: agent.hits for agent in agents_info}
