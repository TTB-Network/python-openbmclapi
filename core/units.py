from datetime import datetime


def format_datetime_from_timestamp(seconds: float):
    return datetime.fromtimestamp(seconds).strftime('%Y-%m-%d %H:%M:%S')