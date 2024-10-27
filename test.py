import asyncio
import aiohttp


URL = "https://saltwood.top:9393/files/PCL-Community/z0z0r4/Image_1726558151857.png"

async def main():
    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(URL) as response:
                print(response.status)
            await asyncio.sleep(1)
asyncio.run(main())