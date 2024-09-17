from sqlalchemy import create_engine, select, Column, Text, BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column, Session, DeclarativeBase
from . import cluster

engine = create_engine(
    "sqlite:///database.db"
)

session = Session(engine)


class Base(DeclarativeBase):
    pass

class HitFiles(Base):
    __tablename__ = "bmclapi_files"

    _id:        Column = Column(Integer, primary_key=True)
    hour:       Column = Column(BigInteger,  default=0)
    id:         Column = Column(Text, nullable=False)
    files:      Column = Column(BigInteger, default=0)
    size:       Column = Column(BigInteger, default=0)
    sync_files: Column = Column(BigInteger, default=0)
    sync_size:  Column = Column(BigInteger, default=0)

async def init():
    engine.connect()
    Base.metadata.create_all(engine)

async def unload():
    engine.dispose()