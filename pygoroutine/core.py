import asyncio
from concurrent.futures import Future
import threading
from typing import Awaitable, Optional, TypeVar


T = TypeVar('T')


class GoroutineExecutor:
    def __init__(self):
        self._lock = threading.Lock()
        self._loop = asyncio.new_event_loop()
        self._worker: Optional[threading.Thread] = None

    
    def _start(self):
        if self._worker:
            return
        with self._lock:
            if self._worker:
                return
            self._worker = threading.Thread(target=self._worker_run, daemon=True)
            self._worker.start()

    
    def _worker_run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()


    def __del__(self):
        self.close()
    
    
    def close(self):
        with self._lock:
            if self._worker and self._worker.is_alive():
                self._loop.call_soon_threadsafe(self._loop.stop)
    
    
    def go(self, co: Awaitable[T]) -> Future[T]:
        self._start()
        return asyncio.run_coroutine_threadsafe(co, self._loop)
    
    
    def do(self, co: Awaitable[T]) -> T:
        return go(co).result()


_executor = GoroutineExecutor()
go = _executor.go
do = _executor.do





