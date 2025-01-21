import asyncio
from collections import defaultdict
from dataclasses import asdict, dataclass
import datetime
from typing import Any, Optional

import anyio
from tqdm import tqdm
from common import logger, env, get_database, telegram_bot
import aiohttp
import urllib.parse as urlparse

import common
from ..base import BaseSync

API_URL = "https://api.papermc.io/v2/"
HTTP_PROXY = env.get("HTTP_PROXY", None)
DATABASE_PREFIX = "papermc"
DATABASE = get_database(f"{DATABASE_PREFIX}")

@dataclass
class ProjectInfo:
    name: str
    project_name: str
    versions: list[str]

@dataclass
class ProjectVersionInfo:
    name: str
    project_name: str
    version_builds: dict[str, list['BuildInfo']]

@dataclass
class BuildInfo:
    build: int
    time: datetime.datetime 
    downloads: list['BuildDownloadInfo']

@dataclass
class BuildDownloadInfo:
    sha256: str
    name: str

@dataclass
class DownloadInfo:
    name: str
    version: str
    build: int
    sha256: str
    asset_name: str

    @property
    def url(self):
        return urlparse.urljoin(
            API_URL,
            f"projects/{self.name}/versions/{self.version}/builds/{self.build}/downloads/{self.asset_name}"
        )


class PaperMCSync(BaseSync):
    def __init__(self):
        self.session: aiohttp.ClientSession = None # type: ignore
        self.collection = DATABASE.get_collection("projects")

    async def init(self):
        self.session = aiohttp.ClientSession(
            proxy=HTTP_PROXY,
        )
        await self.session.__aenter__()
    
    def check_initialized(self):
        if self.session is None:
            raise Exception("PaperMCSync not initialized")

    async def close(self):
        self.check_initialized()
        await self.session.__aexit__(None, None, None)

    async def get_projects(self):
        self.check_initialized()
        async with self.session.get(
            urlparse.urljoin(API_URL, "projects"),
        ) as resp:
            return (await resp.json())['projects']
        
    async def get_project(self, project: str) -> ProjectInfo:
        self.check_initialized()
        async with self.session.get(
            urlparse.urljoin(API_URL, f"projects/{project}"),
        ) as resp:
            data = await resp.json()
            return ProjectInfo(
                project,
                project_name=data['project_name'],
                versions=data['versions'],
            )
    async def get_project_version(self, project_info: ProjectInfo, version: str) -> list[BuildInfo]:
        self.check_initialized()
        async with self.session.get(
            urlparse.urljoin(API_URL, f"projects/{project_info.name}/versions/{version}/builds"),
        ) as resp:
            data = await resp.json()
            builds: list[BuildInfo] = []
            for build in data["builds"]:
                downloads = []
                for download in build["downloads"].values():
                    downloads.append(BuildDownloadInfo(
                        sha256=download["sha256"],
                        name=download["name"],
                    ))
                builds.append(BuildInfo(
                    build=build["build"],
                    time=datetime.datetime.fromisoformat(build["time"]),
                    downloads=downloads,
                ))
            return builds


    async def get_project_versions(self, project_info: ProjectInfo) -> ProjectVersionInfo:
        self.check_initialized()
        results: dict[str, list[BuildInfo]] = {}
        for version, result in zip(project_info.versions, await asyncio.gather(*[self.get_project_version(project_info, version) for version in project_info.versions])):
            results[version] = result
        return ProjectVersionInfo(
            project_info.name,
            project_name=project_info.project_name,
            version_builds=results,
        )

        
        
        
    async def sync(self):
        timings = common.Timings()
        with timings:
            projects = await self.get_projects()
            projects_info = await asyncio.gather(*[self.get_project(project) for project in projects])
            projects_versions = await asyncio.gather(*[self.get_project_versions(project_info) for project_info in projects_info])
        
        logger.success(f"Get list of information about projects: {common.units.format_count_time(timings.get_duration() or 0)}")

        need_downlaods: list[ProjectVersionInfo] = []

        for project in projects_versions:
            new_info = ProjectVersionInfo(
                project.name,
                project_name=project.project_name,
                version_builds=defaultdict(list),
            )
            for version, builds in project.version_builds.items():
                for build in builds:
                    for dl in build.downloads:
                        if await self.collection.find_one({
                            "name": project.name,
                            "project_name": project.project_name,
                            "version": version,
                            "build": build.build,
                            "download": dl.name,
                            "sha256": dl.sha256,
                        }):
                            continue
                        new_info.version_builds[version].append(build)
            if new_info.version_builds:
                need_downlaods.append(new_info)
        messages = []
        for project in need_downlaods:
            for version, builds in project.version_builds.items():
                for build in builds:
                    for dl in build.downloads:
                        messages.append(f"{project.name} {version} {build.build} {dl.name} {dl.sha256}")
        logger.success(f"Get list of need downloads: {sum(sum(len(download) for download in project.version_builds.values()) for project in need_downlaods)}")
        telegram_bot.post_status("sync", "PaperMC", *messages)
        await asyncio.gather(*[self.download(project_version) for project_version in need_downlaods])

    async def download(self, project: ProjectVersionInfo):
        downloads: list[DownloadInfo] = []
        for version, builds in project.version_builds.items():
            for build in builds:
                for dl in build.downloads:
                    downloads.append(
                        DownloadInfo(
                            project.name,
                            version,
                            build.build,
                            dl.sha256,
                            dl.name,
                        )
                    )
        sem = asyncio.Semaphore(1)
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=10)
        ) as session:
            await asyncio.gather(*[self._download(sem, session, info) for info in downloads])
    
    async def _download(self, sem: asyncio.Semaphore, session: aiohttp.ClientSession, info: DownloadInfo):
        if env.dev:
            return
        async with sem, session.get(
            info.url
        ) as resp:
            ...



        
papermc = PaperMCSync()

async def init():
    await papermc.init()

    print(await papermc.sync())


async def shutdown():
    await papermc.close()