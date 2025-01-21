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

def format_bytes(n: float, round: int = 2) -> str:
    i = 0
    for u, un in BYTES_UNITS[1:]:
        if n / un < 1:
            break
        n /= un
        i += 1
    return f'{n:.{round}f}{BYTES_UNITS[i][0]}'

def format_number(n: float, round: int = 2) -> str:
    i = 0
    for u, un in NUMBER_UNITS[1:]:
        if n / un < 1:
            break
        n /= un
        i += 1
    return f'{n:.{round}f}{NUMBER_UNITS[i][0]}'

def format_count_time(n: float, round: int = 2) -> str:
    i = 0
    for u, un in TIME_UNITS[1:]:
        if n / un < 1:
            break
        n /= un
        i += 1
    return f'{n:.{round}f}{TIME_UNITS[i][0]}'
