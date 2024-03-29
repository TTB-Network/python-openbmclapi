from typing import List, Dict
import json
import asyncio
from pathlib import Path
from dataclasses import asdict
from aiowebdav.client import Client
import aiowebdav.exceptions
from core.api import BMCLAPIFile, Storage


class WebDavStorage(Storage):
    def __init__(
        self, webdav_url: str, webdav_username: str, webdav_password: str
    ) -> None:
        self.webdav_url = webdav_url
        self.webdav_username = webdav_username
        self.webdav_password = webdav_password
        self._options: Dict[str, str] = {
            "webdav_url": webdav_url,
            "webdav_username": webdav_username,
            "webdav_password": webdav_password,
        }

    def write_files_json(self, files: List[BMCLAPIFile]) -> None:
        data = {"files": [asdict(file) for file in files]}

        with open("files.json", "w") as json_file:
            json.dump(data, json_file, indent=4)

        print("文件列表已成功写入到 files.json 文件中！")

    async def check_missing_files(self, BMCLAPIfile: Dict[str, List[str]]) -> List[str]:
        print("尝试登录至Webdav服务器")
        try:
            client = Client(
                {
                    "webdav_hostname": self.webdav_url,
                    "webdav_login": self.webdav_username,
                    "webdav_password": self.webdav_password,
                }
            )
        except aiowebdav.exceptions.NoConnection:
            print("无法连接至Webdav服务器，请检查Webdav服务是否开启")

        missing_files = []

        async with Client(**self._options) as client:
            tasks = [
                self.check_file_existence(client, file_path)
                for file_path in BMCLAPIfile["files"]
            ]
            results = await asyncio.gather(*tasks)

        for file_path, file_exists in zip(BMCLAPIfile["files"], results):
            if not file_exists:
                print(f"文件 '{file_path}' 缺失")
                missing_files.append(file_path)
            else:
                print(f"文件 '{file_path}' 检测通过")

        return missing_files

    async def upload_missing_files(self, missing_files: List[str]) -> None:
        client = Client(
            {
                "webdav_hostname": self.webdav_url,
                "webdav_login": self.webdav_username,
                "webdav_password": self.webdav_password,
            }
        )

        async with client as webdav_client:
            upload_tasks = [
                self.upload_file(webdav_client, file) for file in missing_files
            ]
            await asyncio.gather(*upload_tasks)

    async def upload_file(self, client: Client, file: str) -> None:
        local_path = Path("local_directory") / file  # 本地文件路径
        remote_path = Path("remote_directory") / file  # 远程文件路径
        await client.upload(str(local_path), str(remote_path))  # 异步上传文件
        print(f"Uploaded file '{file}'.")

    async def main(self) -> None:
        BMCLAPIfile = [...]
        await self.write_files_json(
            {"files": BMCLAPIfile}
        )  # 将文件列表写入到 files.json

        BMCLAPIfile = await self.read_BMCLAPIfile()
        missing_files = await self.check_missing_files(BMCLAPIfile)

        if missing_files:
            print("缺失文件：")
            for file_path in missing_files:
                print(file_path)
            print("正在准备补全缺失文件")
            # await self.upload_missing_files(missing_files)  # 开发中
        else:
            print("所有文件均已同步")


if __name__ == "__main__":
    webdav_url = "http://127.0.0.1:5244/dav/"
    webdav_username = "admin"
    webdav_password = "I9mEYB07"

    storage = WebDavStorage(webdav_url, webdav_username, webdav_password)
    asyncio.run(storage.main())
