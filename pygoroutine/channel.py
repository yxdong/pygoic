

import asyncio
from asyncio import Future
from collections import deque
from typing import Any, Generic, Optional, Tuple, TypeVar


T = TypeVar('T')


class ChanClosedError(Exception):
    pass


class Chan(Generic[T]):
    def __init__(self, buffsize: int = 0):
        assert buffsize >= 0
        self._buffsize = buffsize
        self._buff = deque[T]()
        self._getters = deque[Future[T]]()
        self._putters = deque[Tuple[Future, T]]()

        self._closed = False
        self._lock = asyncio.Lock()


    async def close(self):
        async with self._lock:
            self._closed = True
            while self._putters:
                fput, item = self._putters.popleft()
                fput.set_exception(ChanClosedError('chan closed'))
            while self._getters:
                fget = self._getters.popleft()
                if self._buff:
                    item = self._buff.popleft()
                    fget.set_result(item)
                else:
                    fget.set_exception(ChanClosedError('chan closed'))


    async def send(self, item: T):
        async with self._lock:
            if self._closed:
                raise ChanClosedError('chan closed')
            fut = asyncio.Future()
            self._putters.append((fut, item))
            self._flush()
        await fut


    async def recv(self) -> Tuple[Optional[T], bool]:
        async with self._lock:
            if self._closed:
                return None, False
            fut = asyncio.Future[T]()
            self._getters.append(fut)
            self._flush()
        try:
            item = await fut
            return item, True
        except ChanClosedError:
            return None, False
            

    def _flush(self):
        while True:
            if self._getters:
                if self._buff:
                    fget = self._getters.popleft()
                    item = self._buff.popleft()
                    fget.set_result(item)

                elif self._putters:
                    fget = self._getters.popleft()
                    fput, item = self._putters.popleft()
                    fget.set_result(item)
                    fput.set_result(None)
                else:
                    break
            
            elif self._putters:
                if len(self._buff) < self._buffsize:
                    fput, item = self._putters.popleft()
                    self._buff.append(item)
                    fput.set_result(None)
                else:
                    break
            else:
                break


    

async def select(*chans: Chan[Any]) -> Tuple[int, Any, bool]: 
    pass