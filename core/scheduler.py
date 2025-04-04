import apscheduler.schedulers.asyncio

scheduler = apscheduler.schedulers.asyncio.AsyncIOScheduler(
    timezone="Asia/Shanghai",
    missfire_grace_time=99999999,
    coalesce=True,
)