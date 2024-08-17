from core.types import Storage, FileInfo, FileList
from core.logger import logger
from core.i18n import locale
from tqdm import tqdm
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

    async def check(self) -> None:
        logger.tinfo("storage.info.check")
        try:
            with tempfile.NamedTemporaryFile(dir=self.path, delete=True) as temp_file:
                temp_file.write(b"")
            logger.tsuccess("storage.success.check")
        except Exception as e:
            raise Exception(locale.t("storage.error.check", e=e))

    async def writeFile(
        self, file: FileInfo, content: io.BytesIO, delay: int, retry: int
    ) -> bool:
        file_path = os.path.join(self.path, file.hash[:2], file.hash)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        for _ in range(retry):
            try:
                async with aiofiles.open(file_path, "wb") as f:
                    await f.write(content.getbuffer())

                if os.path.getsize(file_path) == file.size:
                    return True
                else:
                    logger.terror(
                        "storage.error.write_file.size_mismatch", file=file.hash
                    )
            except Exception as e:
                logger.terror(
                    "storage.error.write_file.retry", file=file.hash, e=e, retry=delay
                )

            await asyncio.sleep(delay)

        logger.terror("storage.error.write_file.failed", file=file.hash)
        return False

    async def getMissingFiles(self, files: FileList, pbar: tqdm) -> FileList:
        if self.checked == True:
            return FileList(files=[])

        async def check_file(file: FileInfo, pbar: tqdm) -> bool:
            pbar.update(1)
            file_path = os.path.join(self.path, file.hash[:2], file.hash)
            try:
                st = await asyncio.to_thread(os.stat, file_path)
                return st.st_size != file.size
            except FileNotFoundError:
                return True

        results = await asyncio.gather(
            *[check_file(file, pbar) for file in files.files]
        )
        missing_files = [
            file for file, is_missing in zip(files.files, results) if is_missing
        ]
        return FileList(files=missing_files)
