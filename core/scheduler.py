import asyncio
import time  
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler  
from apscheduler.schedulers.asyncio import AsyncIOScheduler  
from apscheduler.job import Job

  
# 创建一个全局的同步调度器实例  
sync_scheduler: BackgroundScheduler = None
async_scheduler: AsyncIOScheduler = None
# 存储任务
sync_tasks: dict[int, Job] = {}
async_tasks: dict[int, Job] = {}
cur_id: int = 0

# 根据当前环境创建异步调度器实例  
async def get_async_scheduler() -> AsyncIOScheduler:  
    try:  
        import uvloop  # type: ignore # 尝试导入uvloop，它是一个快速的异步IO库  
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())  
    except ImportError:  
        pass  
    return AsyncIOScheduler()  

async def init():
    global sync_scheduler, async_scheduler
    sync_scheduler = BackgroundScheduler()  
    sync_scheduler.start()  
    
    async_scheduler = await get_async_scheduler()
    async_scheduler.start()

def _add_task_id(job: Job, isasync: bool = False) -> int:
    global sync_tasks, async_tasks, cur_id
    cur = (cur_id := cur_id + 1)
    if isasync:
        async_tasks[cur] = job
    else:
        sync_tasks[cur] = job
    return cur

def is_coroutine(func):  
    return asyncio.iscoroutinefunction(func)  
  
def delay(handler, args = (), kwargs = {}, delay: float = 0) -> int:  
    """  
    安排一个延迟执行的任务。  
    如果handler是异步的，使用异步调度器；否则，使用同步调度器。  
    """  
    def wrapper():  
        handler(*args, **kwargs)  

    async def wrapper_async():  
        await handler(*args, **kwargs)  
      
    if is_coroutine(handler):  
        job = async_scheduler.add_job(wrapper_async, 'date', run_date=datetime.fromtimestamp(time.time() + delay))  
    else:  
        job = sync_scheduler.add_job(wrapper, 'date', run_date=datetime.fromtimestamp(time.time() + delay))  
    return _add_task_id(job, is_coroutine(handler))
  
def repeat(handler, args = (), kwargs = {}, delay: float = 0, interval: float = 0) -> int:  
    """  
    安排一个重复执行的任务。  
    """  
    def wrapper():  
        handler(*args, **kwargs)  

    async def wrapper_async():  
        await handler(*args, **kwargs)  
    
      
    trigger = 'interval' if interval >= 0 else 'date'  
    start_time = time.time() + delay if trigger == 'date' else None  

    if is_coroutine(handler):  
        job = async_scheduler.add_job(wrapper_async, trigger, seconds=interval, next_run_time=start_time)  
    else:  
        job = sync_scheduler.add_job(wrapper, trigger, seconds=interval, next_run_time=start_time)  
    return _add_task_id(job, is_coroutine(handler))
  
def task(handler, sec: float = 0, *args, **kwargs) -> int:  
    def wrapper():  
        handler(*args, **kwargs)  

    async def wrapper_async():  
        await handler(*args, **kwargs)  
    
    if is_coroutine(handler):  
        job = async_scheduler.add_job(wrapper_async, 'date', sec)  
    else:
        job = sync_scheduler.add_job(wrapper, 'date', sec)  
    return _add_task_id(job, is_coroutine(handler))
  
    

def cancel(task_id: int) -> None:
    global sync_tasks, async_tasks
    if task_id in sync_tasks:
        sync_tasks[task_id].remove()
        sync_tasks.pop(task_id)
    if task_id in async_tasks:
        async_tasks[task_id].remove()
        async_tasks.pop(task_id)