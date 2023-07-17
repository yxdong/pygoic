import asyncio
import threading
from asyncio import AbstractEventLoop, Future
from concurrent.futures import Future as ConcurrentFuture, ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar


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
            raise RuntimeError(f"Not allow to call `CoFuture.result` inside a event loop.")
        
        if self._future.done():
            return self._future.result()
        
        future = ConcurrentFuture()
        self._loop.call_soon_threadsafe(self._future_callback, future)
        return future.result(timeout)
        
        
    def exception(self, timeout: Optional[float] = None) -> Optional[BaseException]:
        if asyncio._get_running_loop() is not None:
            raise RuntimeError(f"Not allow to call `CoFuture.exception` inside a event loop.")
        
        if self._future.done():
            return self._future.exception()
        
        future = ConcurrentFuture()
        self._loop.call_soon_threadsafe(self._future_callback, future)
        return future.exception(timeout)


    def _future_callback(self, future: ConcurrentFuture):
        try:
            asyncio.futures._chain_future(self._future, future) # type: ignore
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
        self._pool: Optional[ThreadPoolExecutor] = None

    
    def _init_worker(self):
        if self._worker:
            return
        with self._lock:
            if self._worker:
                return
            self._worker = threading.Thread(target=self._worker_run, daemon=True)
            self._worker.start()


    def _init_pool(self):
        if self._pool:
            return
        with self._lock:
            if self._pool:
                return
            self._pool = ThreadPoolExecutor()

    
    def _worker_run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()


    def __del__(self):
        self.close()
    
    
    def close(self):
        with self._lock:
            if self._worker and self._worker.is_alive():
                self._loop.call_soon_threadsafe(self._loop.stop)
            if self._pool:
                self._pool.shutdown(wait=False)
    
    
    def go(self, coro: Awaitable[T]) -> CoFuture[T]:
        loop = asyncio._get_running_loop()
        if loop is None:
            self._init_worker()
            loop = self._loop
        
        future = asyncio.ensure_future(coro, loop=loop)
        return CoFuture(future, loop)

    
    def do(self, coro: Awaitable[T]) -> T:
        if asyncio._get_running_loop() is not None:
            raise RuntimeError(f"Not allow to call `do` inside a event loop.")
        
        self._init_worker()
        future = asyncio.ensure_future(coro, loop=self._loop)
        cofuture = CoFuture(future, self._loop)
        return cofuture.result()


    async def delegate(self, func: Callable[..., T], *args: Any) -> T:
        self._init_pool()
        return await self._loop.run_in_executor(self._pool, func, *args)



_executor = GoroutineExecutor()


def _get_event_loop() -> AbstractEventLoop:
    loop = asyncio._get_running_loop()
    if loop is None:
        _executor._init_worker()
        return _executor._loop
    else:
        return loop


go = _executor.go
do = _executor.do
delegate = _executor.delegate
