import abc
from dataclasses import dataclass


@dataclass
class Field:
    name: str 
    type: type

class DataBase(abc.ABCMeta):
    @abc.abstractmethod
    def create_table(self, table: str, data: list[Field]):
        raise NotImplementedError
    

class SQLite(DataBase):
    def __init__(self, path: str):
        import sqlite3 as sqlite

        self.database = sqlite.connect(
            path,
            check_same_thread=False
        )
        
        
    @staticmethod
    def parse_type(data: type):
        if isinstance(data, str):
            return "text"
        elif isinstance(data, int):
            return "integer"
    
    def create_table(self, table: str, data: list[Field]):
        self.database.execute(f"create table if not exists {table}()")