import sys
import core
from core.i18n import locale

if __name__ == "__main__":
    version = sys.version_info
    if version < (3, 9):
        print(locale.t("main.unsupported_version", 
                       cur=f"{version.major}.{version.minor}.{version.micro}"))
        exit(0)
    core.init()