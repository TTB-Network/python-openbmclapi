import os
import dotenv

class Env:
    def __init__(self):
        if not dotenv.load_dotenv(dotenv.find_dotenv()):
            raise Exception("No .env file found")
        if self.contains("type"):
            if not dotenv.load_dotenv(f".env.{self.get('type')}"):
                raise Exception(f"No .env.{self.get('type')} file found")
        
    def get(self, key: str, default=None):
        return os.getenv(key, default)
    
    def contains(self, key: str):
        return self.get(key) is not None
    
    def get_int(self, key: str, default=None):
        value = self.get(key, default)
        if value is None:
            return None
        return int(value)

    def get_float(self, key: str, default=None):
        value = self.get(key, default)
        if value is None:
            return None
        return float(value)
    
    def get_bool(self, key: str, default=None):
        value = self.get(key, default)
        if value is None:
            return None
        return value.lower() in ['true', '1', 'yes']
        

    def __contains__(self, key: str) -> bool:
        return self.contains(key)
    
    def __getitem__(self, key: str):
        return self.get(key)


    @property
    def type(self):
        return self.get('type') or "default"
    
    @property
    def dev(self):
        return self.type.lower() == "dev"

env = Env()
__all__ = ['env']
