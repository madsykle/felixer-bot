import time


class Cache:
    def __init__(self, ttl=600):
        self._d: dict = {}
        self._ttl = ttl

    def get(self, key):
        if key in self._d:
            ts, value = self._d[key]
            if time.time() - ts < self._ttl:
                return value
            del self._d[key]
        return None

    def put(self, key, value):
        self._d[key] = (time.time(), value)
