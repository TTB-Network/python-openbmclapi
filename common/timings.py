import time


class Timings:
    def __init__(
        self
    ):
        self._start = None
        self._end = None

    def start(self):
        self._start = time.perf_counter_ns()

    def end(self):
        self._end = time.perf_counter_ns()

    def __enter__(self):
        self._start = time.perf_counter_ns()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._end = time.perf_counter_ns()

    @property
    def finished(self):
        return self._start is not None and self._end is not None

    def get_duration(self):
        if self._start is None or self._end is None:
            return None
        return self._end - self._start
    
    def get_duration_ms(self):
        v = self.get_duration()
        if v is None:
            return None
        return v / 1_000_000.0
    
    def get_duration_s(self):
        v = self.get_duration()
        if v is None:
            return None
        return v / 1_000_000_000.0
    
    def get_duration_us(self):
        v = self.get_duration()
        if v is None:
            return None
        return v / 1_000.0
        