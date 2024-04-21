import sys
import core


if __name__ == "__main__":
    if sys.version_info < (3, 9):
        print(f"Not support version: {sys.version}")
        exit(0)
    core.init()