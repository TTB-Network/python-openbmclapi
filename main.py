import importlib
import io
import json
from pathlib import Path
import queue
import subprocess
import threading
from typing import Optional


def install_module(module_name, module = None):
    module = module or module_name
    try:
        importlib.import_module(module_name)
    except ImportError:
        print(f"正在安装模块 '{module_name}'...")
        subprocess.check_call(["pip", "install", module])
        print(f"模块 '{module_name}' 安装成功")

def init():
    install_module('watchdog')

init()

import sys
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEvent, FileSystemEventHandler
encoding = sys.getdefaultencoding()
process: Optional[subprocess.Popen] = None
stdout = None
stderr = None
output: queue.Queue[bytes] = queue.Queue()
last_output_length: int = 0
last_flush: bool = False
def _():
    global process, stdout, stderr, output
    while 1:
        start_time = time.time()
        process = subprocess.Popen([sys.executable, *sys.argv[2:]], cwd=sys.argv[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.stdout, process.stderr
        process.wait()
        sleep = time.time() - start_time
        if sleep < 5:
            sleep = 5 - sleep
            print(f"Application Error? Sleep {sleep:.2f}s")
            time.sleep(sleep)

def _out():
    global process, stdout, output
    while 1:
        if process and stdout is not None:
            line: bytes = stdout.readline()
            if not line:
                continue
            if line.strip():
                for l in line.split(b"\n"):
                    if l:
                        output.put(l)
            else:
                output.put(line)

def _err():
    global process, stderr, output
    while 1:
        if process and stderr is not None:
            line: bytes = stderr.readline()
            if not line:
                continue
            if line.strip():
                for l in line.split(b"\n"):
                    if l:
                        output.put(l)
            else:
                output.put(line)

def _parse(params):
    kwargs = {}
    if "flush" in params:
        kwargs["flush"] = True
    return kwargs
def _print():
    global output, last_output_length, last_flush
    while 1:
        msg = output.get()
        try:
            msg = msg.decode("utf-8")
        except:
            try:
                msg = msg.decode("gbk")
            except:
                msg = repr(msg)
        msg = msg.removesuffix("\n")
        date = time.localtime()
        date = f"[{date.tm_year:04d}-{date.tm_mon:02d}-{date.tm_mday:02d} {date.tm_hour:02d}:{date.tm_min:02d}:{date.tm_sec:02d}]"
        kwargs: dict = {}
        flush: bool = False
        if msg.startswith("<<<") and ">>>" in msg:
            kwargs = _parse(msg[3:msg.find(">>>")])
            msg = msg[msg.find(">>>") + 3:]
            flush = kwargs.get("flush", False)
        text = f"{date} {msg}"
        if flush:
            sys.stdout.write('\r' + ' ' * (last_output_length + 16) + '\r')
            sys.stdout.flush()
            last_output_length = len(text)
        print(text + ('\n' if not flush else ''), end='', flush=flush)
        last_flush = flush

class MyHandler(FileSystemEventHandler):
    def on_any_event(self, event: FileSystemEvent) -> None:
        global process
        if not event.is_directory and event.src_path.endswith('.py'):
            if process is None or process.poll() != None:
                return
            print(f"The container file have been changed! File: {event.src_path}")
            process.kill()
            process.terminate()
if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Not Container Path.")
        exit(0)
    if len(sys.argv) == 2:
        print("Not Executable File.")
        exit(0)
    path = sys.argv[1]
    if not Path(path).exists():
        Path(path).mkdir(exist_ok=True, parents=True)
    event_handler = MyHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    threading.Thread(target=_).start()
    threading.Thread(target=_err).start()
    threading.Thread(target=_out).start()
    threading.Thread(target=_print).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()