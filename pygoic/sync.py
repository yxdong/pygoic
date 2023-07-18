
from __future__ import annotations
import asyncio
import threading
from asyncio import Future as AsyncFuture
from concurrent.futures import Future as ConcurrentFuture


class WaitGroup:
    def __init__(self, initstate: int = 0):
        if initstate < 0:
            raise Exception("negative WaitGroup counter")
        self._state: int = initstate
        self._waiters: int = 0
        self._lock = threading.Lock()
        self._future: ConcurrentFuture = ConcurrentFuture()
        
        
    def add(self, delta: int):
        with self._lock:
            if self._waiters > 0 and delta > 0:
                raise Exception("WaitGroup misuse: Add called concurrently with Wait")
            if self._state + delta < 0:
                raise Exception("negative WaitGroup counter")
            
            self._state += delta
            if self._state == 0 and self._waiters > 0:
                self._future.set_result(None)
                self._future = ConcurrentFuture()
                self._waiters = 0
                
                
    def done(self):
        self.add(-1)
        
        
    async def wait(self):
        with self._lock:
            if self._state == 0:
                return
            afut: AsyncFuture = asyncio.wrap_future(self._future)
            self._waiters += 1
        await afut
