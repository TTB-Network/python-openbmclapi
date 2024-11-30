from datetime import datetime

NUMBER_UNITS = (
    ('', 1),
    ('K', 1e3),
    ('M', 1e3),
    ('G', 1e3),
    ('T', 1e3),
    ('P', 1e3),
    ('E', 1e3),
    ('Z', 1e3),
    ('Y', 1e3),
)

TIME_UNITS = (
    ('ns', 1),
    ('μs', 1e3),
    ('ms', 1e3),
    ('s', 1e3),
    ('min', 60),
    ('h', 60),
)
# 1024
BYTES_UNITS = (
    ('iB', 1),
    ('KiB', 1024),
    ('MiB', 1024),
    ('GiB', 1024),
    ('TiB', 1024),
    ('PiB', 1024),
    ('EiB', 1024),
    ('ZiB', 1024),
    ('YiB', 1024)
)

def format_bytes(n: float) -> str:
    i = 0
    for u, un in BYTES_UNITS[1:]:
        if n / un < 1:
            break
        n /= un
        i += 1
    return f'{n:.2f}{BYTES_UNITS[i][0]}'


def format_number(n: float) -> str:
    i = 0
    for u, un in NUMBER_UNITS[1:]:
        if n / un < 1:
            break
        n /= un
        i += 1
    return f'{n:.2f}{NUMBER_UNITS[i][0]}'


def format_count_time(n: float, round: int = 2) -> str:
    i = 0
    for u, un in TIME_UNITS[1:]:
        if n / un < 1:
            break
        n /= un
        i += 1
    return f'{n:.{round}f}{TIME_UNITS[i][0]}'

def format_count_datetime(secs: float) -> str:
    ms = int(secs * 1000)
    s = int(ms / 1000) % 60
    m = int(ms / (1000 * 60)) % 60
    h = int(ms / (1000 * 60 * 60)) % 24
    d = int(ms / (1000 * 60 * 60 * 24))
    if d > 0:
        return f'{d:02d}:{h:02d}:{m:02d}:{s:02d}'
    if h > 0:
        return f'{h:02d}:{m:02d}:{s:02d}'
    else:
        return f'{m:02d}:{s:02d}'


def format_datetime_from_timestamp(seconds: float):
    return datetime.fromtimestamp(seconds).strftime('%Y-%m-%d %H:%M:%S')