import math


_BYTES_ = ("B", "KB", "MB", "GB", "TB", "PB", "EB")
_NUMBER_ = ("", "k", "M", "G", "T", "P", "E")

def format_bytes(size):
    if size == 0:
        return f"{size:.2f}{_BYTES_[0]}"
    i = min(int(math.floor(math.log(size, 1024))), len(_BYTES_))
    if i != 0:
        size = round(size / (1024 ** i), 2)
    return f"{size}{_BYTES_[i]}"

def format_bits(size):
    return format_bytes(size * 8)

def format_number(number):
    if number == 0:
        return f"{number}{_NUMBER_[0]}"
    i = min(int(math.floor(math.log(number, 1000))), len(_NUMBER_), 1)
    if i != 0:
        number = round(number // (1000 ** i), 2)
    return f"{number}{_NUMBER_[i]}"

def format_numbers(*numbers):
    number = max(*numbers)
    if number == 0:
        return (f"{number}{_NUMBER_[0]}" for number in numbers)
    i = min(int(math.floor(math.log(number, 1000))), len(_NUMBER_), 1)
    if i != 0:
        return (f"{round(number // (1000 ** i), 2)}{_NUMBER_[i]}" for number in numbers)
    return (f"{number}{_NUMBER_[i]}" for number in numbers)

