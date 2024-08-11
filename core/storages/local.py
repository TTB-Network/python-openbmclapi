from core.utils import Storage, FileInfo, FileList
import os
import io
import aiofiles
import asyncio
import tempfile

class LocalStorage(Storage):
    def __init__(self, path: str) -> None:
        self.path = path
        self.checked = False
    
    async def init(self) -> None:
        if not os.path.exists(self.path):
            os.makedirs(self.path)

    async def check(self) -> bool:
        try:
            with tempfile.NamedTemporaryFile(dir=self.path, delete=True) as temp_file:
                temp_file.write(b'')
            return True
        except Exception:
            return False

    async def writeFile(self, file: FileInfo, content: io.BytesIO) -> int:
        async with aiofiles.open(os.join(self.path, file.hash[:2], file.hash), 'wb') as f:
            await f.write(content.getbuffer())
            return len(content.getbuffer())
        
    async def getMissingFiles(self, files: FileList) -> FileList:
        if self.checked == True:
            return FileList(files=[])
        async def check_file(file: FileInfo) -> bool:
            file_path = os.path.join(self.path, file.hash[:2], file.hash)
            try:
                st = await asyncio.to_thread(os.stat, file_path)
                return st.st_size != file.size
            except FileNotFoundError:
                return True
        results = await asyncio.gather(*[check_file(file) for file in files.files])
        missing_files = [file for file, is_missing in zip(files.files, results) if is_missing]
        return missing_files
    