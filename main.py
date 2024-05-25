import sys

if __name__ == "__main__":
    version = sys.version_info
    from core.i18n import locale
    if version < (3, 12):
        print(locale.t("main.unsupported_version", 
                       cur=f"{version.major}.{version.minor}.{version.micro}"))
        exit(0)
    import core
    core.init()