import asyncio
import anyio
from common import logger
from common import Timings, units
import common
from . import modrinth, papermc

PROJECT_NAME = "Sync"

def init():
    anyio.run(main)


async def module_exec(
    *modules,
    exec: str,
    name: str,
):
    logger.info(f"{exec}ing {len(modules)} module(s)...")
    timing = Timings()
    with timing:
        async with anyio.create_task_group() as task_group:
            for module in modules:
                func = getattr(module, name, None)
                if func is None:
                    continue
                task_group.start_soon(func)
    logger.info(f"{exec}ed modules, total {units.format_count_time(timing.get_duration() or -1)}.")

async def main():
    logger.info("=" * 32 + f" [{PROJECT_NAME}] " + "=" * 32)

    # load modules
    await module_exec(
        papermc,
        modrinth,
        exec="Load",
        name="init"
    )
    try:
        await asyncio.get_event_loop().create_future()
    except asyncio.CancelledError:
        pass

    await module_exec(
        papermc,
        modrinth,
        exec="Unload",
        name="shutdown"
    )

    await common.shutdown()


