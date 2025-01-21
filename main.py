import sys


if __name__ == "__main__":
    if len(sys.argv) <= 1 or sys.argv[1] not in ("sync", "backend"):
        print("Usage: python main.py sync")
        print("Usage: python main.py backend")
        sys.exit(1)

    if sys.argv[1] == "sync":
        import sync
        sync.init()
    elif sys.argv[1] == "backend":
        import backend

        backend.init()
