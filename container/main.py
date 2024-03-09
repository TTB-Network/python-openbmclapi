import importlib
import subprocess

def install_module(module_name, module = None):
    module = module or module_name
    try:
        importlib.import_module(module_name)
    except ImportError:
        print(f"正在安装模块 '{module_name}'...")
        subprocess.check_call(["pip", "install", module])
        print(f"模块 '{module_name}' 安装成功")

def init():
    install_module('socketio')
    install_module('aiohttp')
    install_module("hmac")
    install_module("pyzstd")
    install_module("avro", "avro-python3")

init()

if __name__ == "__main__":
    import web
    web.init()