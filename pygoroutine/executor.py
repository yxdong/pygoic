import asyncio
import threading
from asyncio import AbstractEventLoop, Future
from concurrent.futures import Future as ConcurrentFuture
from typing import Any, Awaitable, Generic, Optional, TypeVar


T = TypeVar('T')


class CoFuture(Generic[T]):
    def __init__(self, future: Future[T], loop: AbstractEventLoop):
        self._future = future
        self._loop = loop


    def cancelled(self) -> bool:
        return self._future.cancelled()
    
    
    def done(self) -> bool:
        return self._future.done()
    
    
    def result(self, timeout: Optional[float] = None) -> T:
        if asyncio._get_running_loop() is not None:
            raise RuntimeError(f"Function `CoFuture.result` can't work in event loop.")
        
        if self._future.done():
            return self._future.result()
        
        future = ConcurrentFuture()
        self._loop.call_soon_threadsafe(self._future_callback, future)
        return future.result(timeout)
        
        
    def exception(self, timeout: Optional[float] = None) -> Optional[BaseException]:
        if asyncio._get_running_loop() is not None:
            raise RuntimeError(f"Function `CoFuture.exception` can't work in event loop.")
        
        if self._future.done():
            return self._future.exception()
        
        future = ConcurrentFuture()
        self._loop.call_soon_threadsafe(self._future_callback, future)
        return future.exception(timeout)


    def _future_callback(self, future: ConcurrentFuture):
        try:
            asyncio.futures._chain_future(self._future, future)
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:
            if future.set_running_or_notify_cancel():
                future.set_exception(exc)
            raise


    def __await__(self):
        return self._future.__await__()


    def __iter__(self):
        return self._future.__iter__()
    
        
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
    
    
    def go(self, coro: Awaitable[T]) -> CoFuture[T]:
        loop = asyncio._get_running_loop()
        if loop is None:
            self._start()
            loop = self._loop
        
        future = asyncio.ensure_future(coro, loop=loop)
        return CoFuture(future, loop)

    
    def do(self, coro: Awaitable[T]) -> T:
        if asyncio._get_running_loop() is not None:
            raise RuntimeError(f"Function `do` can't work in event loop.")
        
        self._start()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()


_executor = GoroutineExecutor()
go = _executor.go
do = _executor.do





