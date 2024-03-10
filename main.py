import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import traceback
from typing import Optional
import sys
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEvent, FileSystemEventHandler

class PrintColor:
    def __init__(self) -> None:
        self.ansi = (  
            (sys.platform != 'Pocket PC') and  
            (  
                (sys.platform != 'win32') or  
                ('ANSICON' in os.environ)  
            ) and  
            (  
                sys.stdout.isatty() or  
                (sys.platform == 'win32')  
            ) and  
            (  
                'TERM' not in os.environ or  
                (  
                    os.environ['TERM'].lower() in ('xterm', 'linux', 'screen', 'vt100', 'cygwin', 'ansicon') and  
                    os.environ['TERM'].lower() not in ('dumb', 'emacs', 'emacs-24', 'xterm-mono')  
                )  
            )  
        )
        self.colors = {  
            'reset': '\033[0m',  
            'red': '\033[31m',  
            'green': '\033[32m',  
            'yellow': '\033[33m',  
            'blue': '\033[34m',  
            'magenta': '\033[35m',  
            'cyan': '\033[36m',  
            'white': '\033[37m',  
            'black': '\033[30m',  
        }  
        self.open_tag_pattern = r'<(\w+)>'  
        self.close_tag_pattern = r'<(\w+)/>'  

    def parse(self, text: str):  
        current_color = self.colors['reset']  
        open_tags = re.findall(self.open_tag_pattern, text)  
        for tag in open_tags:  
            if tag in self.colors:  
                text = text.replace(f'<{tag}>', self.colors[tag], 1)  
                current_color = self.colors[tag]  
            else:  
                text = text.replace(f'<{tag}>', '', 1)  
        close_tags = re.findall(self.close_tag_pattern, text)  
        for tag in close_tags:  
            if tag == tag.lower() and self.colors.get(tag.lower(), '') == current_color:  
                text = text.replace(f'<{tag}/>', self.colors['reset'], 1)  
                current_color = self.colors['reset']  
        return text  

printColor = PrintColor()    
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

def _parse(params: str):
    kwargs = {}
    for item in params.split(","):
        if ':' not in item:
            continue
        k, v = item.split(":", 1)
        if v == "True":
            v = True
        elif v == "False":
            v = False
        else:
            try:
                v = float(v)
            except:
                try:
                    v = int(v)
                except:
                    ...
        kwargs[k] = v
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
        try:
            msg = msg.removesuffix("\n")
            date = time.localtime()
            kwargs: dict = {}
            flush: bool = False
            if msg.startswith("<<<") and ">>>" in msg:
                kwargs = _parse(msg[3:msg.find(">>>")])
                msg = msg[msg.find(">>>") + 3:]
                flush = kwargs.get("flush", False)
                if 'time' in kwargs:
                    date = time.localtime(kwargs["time"])
            date = f"[{date.tm_year:04d}-{date.tm_mon:02d}-{date.tm_mday:02d} {date.tm_hour:02d}:{date.tm_min:02d}:{date.tm_sec:02d}]"
            text = printColor.parse(f"<{kwargs.get('color', 'reset')}>{date} {msg}")
            if flush:
                sys.stdout.write('\r' + ' ' * (last_output_length + 16) + '\r')
                sys.stdout.flush()
                last_output_length = len(text)
            print(text + ('\n' if not flush else ''), end='', flush=flush)
            last_flush = flush
        except:
            traceback.print_exc()
            ...

class MyHandler(FileSystemEventHandler):
    def on_any_event(self, event: FileSystemEvent) -> None:
        global process
        if not event.is_directory and event.src_path.endswith('.py'):
            if process is None or process.poll() != None:
                return
            print(f"The container file have been changed! File: {event.src_path}")
            _kill()
def _kill():
    global process
    if process is None or process.poll() != None:
        return
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
    _kill()