import sqlite3
from typing import Any

__METHODS__ = ['query', 'queryAllData', 'execute', 'executemany', 'connect', 'disconnect', "raw_execute", "commit"]

db = None

def query(cmd: str, *params) -> list[Any]:
    global db
    cur = db.execute(cmd, params)
    return cur.fetchone() or []


def queryAllData(cmd: str, *params) -> list[tuple]:
    global db
    cur = db.execute(cmd, params)
    return cur.fetchall() or []


def execute(cmd: str, *params) -> None:
    global db
    db.execute(cmd, params)
    db.commit()


def executemany(*cmds: tuple[str, tuple[Any, ...]]) -> None:
    global db
    for cmd in cmds:
        db.execute(*cmd)
    db.commit()


def connect():
    global db
    db = sqlite3.connect("./data/database.db", check_same_thread=False)

def disconnect():
    global db
    db.commit()
    db.close()

def raw_execute(cmd: str, *params) -> None:
    global db
    db.execute(cmd, params)

def commit():
    global db
    db.commit()