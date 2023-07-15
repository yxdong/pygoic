

from abc import ABC, abstractmethod
import asyncio
from asyncio import Future
from collections import deque
import random
import threading
from typing import Any, Generic, Optional, Tuple, TypeVar


T = TypeVar('T')


class ChanClosedError(Exception):
    pass


class _ChanGetter(ABC, Generic[T]):
    @abstractmethod
    def set(self, item: T) -> bool:
        pass
    
    @abstractmethod
    def close(self) -> bool:
        pass


class _SingleChanGetter(_ChanGetter[T]):
    def __init__(
        self,
        future: asyncio.Future[Tuple[Optional[T], bool]],
    ):
        self._future = future
    
    def set(self, item: T) -> bool:
        self._future.set_result((item, True))
        return True

    def close(self) -> bool:
        self._future.set_result((None, False))
        return True
    

class _MultiChanGetter(_ChanGetter[Any]):
    def __init__(
        self, 
        seq: int, 
        future: asyncio.Future[Tuple[int, Any, bool]],
        lock: threading.Lock,
    ):
        self._seq = seq
        self._future = future
        self._lock = lock
        
        
    def _set_result(self, item: Any, ok: bool) -> bool:
        if self._future.done():
            return False
        locked = self._lock.acquire(blocking=False)
        if locked:
            try:
                if self._future.done():
                    return False
                self._future.set_result((self._seq, item, ok))
                return True

            finally:
                self._lock.release()
        else:
            return False
        
        
    def set(self, item: Any) -> bool:
        return self._set_result(item, True)
    
    
    def close(self) -> bool:
        return self._set_result(None, False)



class Chan(Generic[T]):
    def __init__(self, buffsize: int = 0):
        assert buffsize >= 0
        self._buffsize = buffsize
        self._buff = deque[T]()
        self._getters = deque[_ChanGetter[T]]()  # TODO: use LinkedList
        self._putters = deque[Tuple[Future[None], T]]()

        self._closed = False
        self._lock = threading.Lock()


    def close(self):
        with self._lock:
            self._closed = True
            while self._putters:
                futput, item = self._putters.popleft()
                futput.set_exception(ChanClosedError('chan closed'))
            while self._getters:
                getter = self._getters.popleft()
                if self._buff:
                    item = self._buff[0]
                    if getter.set(item):
                        self._buff.popleft()
                else:
                    getter.close()


    async def send(self, item: T):
        with self._lock:
            if self._closed:
                raise ChanClosedError('chan closed')
            
            fut = asyncio.Future[None]()
            self._putters.append((fut, item))
            self._flush()
            
        await fut


    async def recv(self) -> Tuple[Optional[T], bool]:
        with self._lock:
            if self._closed:
                if self._buff:
                    item = self._buff.popleft()
                    return item, True
                else:
                    return None, False
            
            fut = asyncio.Future[Tuple[Optional[T], bool]]()
            getter = _SingleChanGetter[T](fut)
            self._getters.append(getter)
            self._flush()
            
        return await fut


    def send_nowait(self, item: T) -> bool:
        with self._lock:
            if self._closed:
                raise ChanClosedError('chan closed')
            
            self._flush()
            while self._getters:
                getter = self._getters.popleft()
                if getter.set(item):
                    return True
                
            if len(self._buff) < self._buffsize:
                self._buff.append(item)
                return True
            else:
                return False


    def recv_nowait(self) -> Tuple[bool, Optional[T], bool]:
        ''' Return: (success, item, ok)
        '''
        with self._lock:
            if self._closed:
                if self._buff:
                    item = self._buff.popleft()
                    return True, item ,True
                else:
                    return True, None, False
            else:
                if self._buff:
                    item = self._buff.popleft()
                    self._flush()
                    return True, item, True
                
                elif self._putters:
                    futput, item = self._putters.popleft()
                    self._flush()
                    futput.set_result(None)
                    return True, item, True
                
                else:
                    return False, None, False


    def _flush(self):
        while True:
            if self._getters:
                if self._buff:
                    getter = self._getters.popleft()
                    item = self._buff[0]
                    if getter.set(item):
                        self._buff.popleft()

                elif self._putters:
                    getter = self._getters.popleft()
                    futput, item = self._putters[0]
                    if getter.set(item):
                        self._putters.popleft()
                        futput.set_result(None)
                else:
                    break
            
            elif self._putters:
                if len(self._buff) < self._buffsize:
                    futput, item = self._putters.popleft()
                    self._buff.append(item)
                    futput.set_result(None)
                else:
                    break
            else:
                break
    

    def _hook_getter(self, getter: _ChanGetter[T]):
        with self._lock:
            if self._closed:
                if self._buff:
                    item = self._buff[0]
                    if getter.set(item):
                        self._buff.popleft()
                else:
                    getter.close()
            else:
                self._getters.append(getter)
                self._flush()


    def __aiter__(self):
        return self
    

    async def __anext__(self) -> T:
        item, ok = await self.recv()
        if ok:
            return item # type: ignore
        else:
            raise StopAsyncIteration



class _NilChan(Chan[T]):
    def close(self):
        raise Exception('closing nil chan')
    
    async def send(self, item: T):
        fut = asyncio.Future()
        await fut

    async def recv(self) -> Tuple[Optional[T], bool]:
        fut = asyncio.Future[Tuple[Optional[T], bool]]()
        return await fut

    def send_nowait(self, item: T) -> bool:
        return False

    def recv_nowait(self) -> Tuple[bool, Optional[T], bool]:
        return False, None, False

    def _hook_getter(self, getter: _ChanGetter[T]):
        pass


nilchan = _NilChan()


async def select(*chans: Chan[Any], default: bool = False) -> Tuple[int, Any, bool]:
    shuffled_chans = list(chans)
    random.shuffle(shuffled_chans)

    if default:
        for i, ch in enumerate(shuffled_chans):
            success, item, ok = ch.recv_nowait()
            if success:
                return i, item, ok
        return -1, None, False

    else:
        fut = asyncio.Future[Tuple[int, Any, bool]]()
        lock = threading.Lock()
        for i, ch in enumerate(shuffled_chans):
            getter = _MultiChanGetter(i, fut, lock)
            ch._hook_getter(getter)
            if fut.done():
                return await fut
        return await fut
