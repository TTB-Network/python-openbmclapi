from datetime import datetime

NUMBER_UNITS = (
    ('', 1),
    ('K', 1e3),
    ('M', 1e6),
    ('G', 1e9),
    ('T', 1e12),
    ('P', 1e15),
    ('E', 1e18),
    ('Z', 1e21),
    ('Y', 1e24),
)

TIME_UNITS = (
    ('ns', 1),
    ('μs', 1e3),
    ('ms', 1e6),
    ('s', 1e9),
    ('min', 6e10),
    ('h', 3.6e12),
)
# 1024
BYTES_UNITS = (
    ('iB', 1),
    ('KiB', 1024),
    ('MiB', 1024**2),
    ('GiB', 1024**3),
    ('TiB', 1024**4),
    ('PiB', 1024**5),
    ('EiB', 1024**6),
    ('ZiB', 1024**7),
    ('YiB', 1024**8)
)

def format_bytes(n: float) -> str:
    i = 0
    while n >= 1024 and i < len(BYTES_UNITS) - 1:
        n /= 1024
        i += 1
    return f'{n:.2f}{BYTES_UNITS[i][0]}'


def format_number(n: float) -> str:
    i = 0   
    while n >= 1000 and i < len(NUMBER_UNITS) - 1:
        n /= 1000
        i += 1
    return f'{n:.2f}{NUMBER_UNITS[i][0]}'


def format_count_time(n: float) -> str:
    i = 0
    for unit, t in TIME_UNITS:
        if n < t:
            break
        n /= t
        i += 1
    return f'{n:.2f}{TIME_UNITS[i][0]}'

def format_count_datetime(secs: float) -> str:
    ms = int(secs * 1000)
    s = int(ms / 1000) % 60
    m = int(ms / (1000 * 60)) % 60
    h = int(ms / (1000 * 60 * 60))
    if h > 0:
        return f'{h:02d}:{m:02d}:{s:02d}'
    else:
        return f'{m:02d}:{s:02d}'


def format_datetime_from_timestamp(seconds: float):
    return datetime.fromtimestamp(seconds).strftime('%Y-%m-%d %H:%M:%S')