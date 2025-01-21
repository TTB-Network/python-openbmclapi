from dataclasses import asdict, dataclass
import datetime
from typing import Optional

from tqdm import tqdm
from common import logger, env, get_database
import aiohttp
import urllib.parse as urlparse

API_URL = "https://staging-api.modrinth.com/v2/"
HTTP_PROXY = env.get("HTTP_PROXY", None)
DATABASE_PREFIX = "modrinth"
DATABASE = get_database(f"{DATABASE_PREFIX}")
@dataclass
class SearchProject:
    project_id: str
    project_type: str
    slug: str
    author: str
    title: str
    description: str
    categories: list[str]
    display_categories: Optional[list[str]]
    versions: list[str]
    date_created: datetime.datetime
    date_modified: datetime.datetime
    latest_version: Optional[str]
    license: str
    client_side: str
    server_side: str
    color: Optional[str]

class Search:
    def __init__(
        self,
    ):
        self.session: Optional[aiohttp.ClientSession] = None

    async def init(self):
        self.session = aiohttp.ClientSession(
            proxy=HTTP_PROXY,
        )
        await self.session.__aenter__()


    async def get_total(self):
        if self.session is None:
            raise Exception("Search not initialized")
        async with self.session.get(
            urlparse.urljoin(
                API_URL,
                "search",
            ),
            params = {
                "limit": 1
            }
        ) as resp:
            data = await resp.json()
            return data["total_hits"]
        
    async def get_searchs(self, total: int):
        if self.session is None:
            raise Exception("Search not initialized")
        for i in range(0, total, 100):
            async with self.session.get(
                urlparse.urljoin(
                    API_URL,
                    "search",
                ),
                params = {
                    "limit": min(total - i, 100),
                    "offset": i
                }
            ) as resp:
                data = await resp.json()
                hits = data["hits"]
                for hit in hits:
                    try:
                        yield SearchProject(
                            project_id=hit["project_id"],
                            project_type=hit["project_type"],
                            slug=hit["slug"],
                            author=hit["author"],
                            title=hit["title"],
                            description=hit["description"],
                            categories=hit["categories"],
                            display_categories=hit["display_categories"],
                            versions=hit["versions"],
                            date_created=datetime.datetime.fromisoformat(hit["date_created"]),
                            date_modified=datetime.datetime.fromisoformat(hit["date_modified"]),
                            latest_version=hit["latest_version"],
                            license=hit["license"],
                            client_side=hit["client_side"],
                            server_side=hit["server_side"],
                            color=f"#{hit["color"]:06x}" if hit["color"] is not None else None,
                        )
                    except:
                        logger.error(f"Error while parsing search data: {hit}")
                        logger.traceback()

    async def sync_searches(self):
        total = await self.get_total()
        collection = DATABASE.get_collection("search")
        with tqdm(
            total=total,
            desc="Syncing search",
        ) as pbar:
            async for data in self.get_searchs(total):
                pbar.set_postfix_str(data.project_id + " " + data.title)
                if await collection.find_one({"project_id": data.project_id}) is None:
                    await collection.insert_one(asdict(data))
                pbar.update(1)
            


    async def close(self):
        if self.session is None:
            return
        await self.session.__aexit__(None, None, None)

search = Search()

async def init():
    await search.init()
    logger.success("Modrinth search initialized")
    logger.info("Start syncing search")
    await search.sync_searches()


async def shutdown():
    await search.close()