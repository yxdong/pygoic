
from __future__ import annotations
import asyncio
import threading
from asyncio import AbstractEventLoop, Future as AsyncFuture
from concurrent.futures import Future as ConcurrentFuture, ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar


T = TypeVar('T')

# TODO: only awaitable is enought

class CoFuture(Generic[T]):
    def __init__(self, future: ConcurrentFuture[T], loop: AbstractEventLoop):
        self._future = future
        self._loop = loop

    def cancelled(self) -> bool:
        return self._future.cancelled()
    
    def running(self) -> bool:
        return self._future.running()
    
    def done(self) -> bool:
        return self._future.done()
    
    def result(self, timeout: Optional[float] = None) -> T:
        if asyncio._get_running_loop() is not None:
            raise RuntimeError(f"Not allow to call `CoFuture.result` inside a event loop.")
        else:
            return self._future.result(timeout)
        
    def exception(self, timeout: Optional[float] = None) -> Optional[BaseException]:
        if asyncio._get_running_loop() is not None:
            raise RuntimeError(f"Not allow to call `CoFuture.exception` inside a event loop.")
        else:
            return self._future.exception(timeout)

    def __await__(self):
        afut = asyncio.wrap_future(self._future, loop=self._loop)
        return afut.__await__()

    __iter__ = __await__



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


    def _get_event_loop(self) -> AbstractEventLoop:
        loop = asyncio._get_running_loop()
        if loop is None:
            self._init_worker()
            return self._loop
        else:
            return loop


    def _future_callback(self, afut: AsyncFuture, cfut: ConcurrentFuture):
        try:
            asyncio.futures._chain_future(afut, cfut) # type: ignore
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:
            if cfut.set_running_or_notify_cancel():
                cfut.set_exception(exc)
            raise


    def __del__(self):
        self.close()
    
    
    def close(self):
        with self._lock:
            if self._worker and self._worker.is_alive():
                self._loop.call_soon_threadsafe(self._loop.stop)
            if self._pool:
                self._pool.shutdown(wait=False)
    
    
    def go(self, coro: Awaitable[T]) -> CoFuture[T]:
        loop = self._get_event_loop()
        afut = asyncio.ensure_future(coro, loop=loop)
        cfut = ConcurrentFuture()
        loop.call_soon_threadsafe(self._future_callback, afut, cfut)
        return CoFuture(cfut, loop)

    
    def do(self, coro: Awaitable[T]) -> T:
        if asyncio._get_running_loop() is not None:
            raise RuntimeError(f"Not allow to call `do` inside a event loop.")
        else:
            self._init_worker()
            
        afut = asyncio.ensure_future(coro, loop=self._loop)
        cfut = ConcurrentFuture()
        self._loop.call_soon_threadsafe(self._future_callback, afut, cfut)
        return cfut.result()


    async def delegate(self, func: Callable[..., T], *args: Any) -> T:
        self._init_pool()
        return await self._loop.run_in_executor(self._pool, func, *args)



_executor = GoroutineExecutor()
_get_event_loop = _executor._get_event_loop
go = _executor.go
do = _executor.do
delegate = _executor.delegate
