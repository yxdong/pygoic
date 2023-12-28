
from __future__ import annotations
from abc import ABC, abstractmethod
import asyncio
from collections import deque
from threading import Lock
from typing import Any, Generic, List, Optional, Tuple, TypeVar, Deque, Union
from .linked import LinkedList, LinkedNode


T = TypeVar('T')


# exceptions

class ChanClosedError(Exception):
    pass


# abstract of chan item reader / writer

class _ChanItemReader(ABC, Generic[T]):
    @abstractmethod
    def put(self, item: T, ok: bool):
        pass
    
    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def getlock(self) -> Optional[Lock]:
        pass
    
    @abstractmethod
    def discarded(self) -> bool:
        pass
    

class _ChanItemWriter(ABC, Generic[T]):
    @abstractmethod
    def take(self) -> T:
        pass
    
    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def getlock(self) -> Optional[Lock]:
        pass
    
    @abstractmethod
    def discarded(self) -> bool:
        pass
    

# simple chan item reader / writer

class _SimpleChanItemReader(_ChanItemReader[T]):
    def __init__(self):
        self._future: asyncio.Future[Tuple[Optional[T], bool]] = asyncio.Future()

    async def read(self) -> Tuple[Optional[T], bool]:
        return await self._future
        
    def put(self, item: T, ok: bool):
        self._future.set_result((item, ok))

    def close(self):
        self._future.set_result((None, False))

    def getlock(self) -> Optional[Lock]:
        return None
    
    def discarded(self) -> bool:
        return False


class _SimpleChanItemWriter(_ChanItemWriter[T]):
    def __init__(self, item: T):
        self._item = item
        self._future: asyncio.Future[None] = asyncio.Future()

    async def write(self):
        await self._future
    
    def take(self) -> T:
        self._future.set_result(None)
        return self._item

    def close(self):
        self._future.set_exception(ChanClosedError('chan closed'))

    def getlock(self) -> Optional[Lock]:
        return None
    
    def discarded(self) -> bool:
        return False


# mutex reader / writer group

class _GeminiLock:
    def __init__(self, lock_1: Lock, lock_2: Lock):
        assert lock_1 is not lock_2
        if id(lock_1) < id(lock_2):
            self._lock_1 = lock_1
            self._lock_2 = lock_2
        else:
            self._lock_1 = lock_2
            self._lock_2 = lock_1
        
    def __enter__(self):
        self._lock_1.acquire()
        self._lock_2.acquire()
        return self
    
    def __exit__(self, exc_type, exc_value, trace):
        self._lock_2.release()
        self._lock_1.release()


class _MutexGroup:
    def __init__(self):
        self._lock = Lock()
        self._future: asyncio.Future[Tuple[int, Any, bool]] = asyncio.Future()
        self._nodes: List[Tuple[LinkedNode, Chan]] = []

    def getlock(self) -> Lock:
        return self._lock
    
    def done(self) -> bool:
        return self._future.done()
    
    def set_result(self, id: int, item: Any, ok: bool):
        self._future.set_result((id, item, ok))
    
    def set_exception(self, ex: Exception):
        self._future.set_exception(ex)

    def add_node(self, node: LinkedNode, chan: Chan):
        self._nodes.append((node, chan))

    def release(self):
        for node, chan in self._nodes:
            if node.list is not None:
                with chan._lock:
                    node.delete()


class _MutexChanItemReader(_ChanItemReader[T]):
    def __init__(self, id: int, group: _MutexGroup):
        self._id = id
        self._group = group

    def put(self, item: T, ok: bool):
        self._group.set_result(self._id, item, ok)
    
    def close(self):
        self._group.set_result(self._id, None, False)

    def getlock(self) -> Optional[Lock]:
        return self._group.getlock()
    
    def discarded(self) -> bool:
        return self._group.done()


class _MutexChanItemWriter(_ChanItemWriter[T]):
    def __init__(self, id: int, item: T, group: _MutexGroup):
        self._item = item
        self._id = id
        self._group = group

    def take(self) -> T:
        self._group.set_result(self._id, self._item, True)
        return self._item
    
    def close(self):
        self._group.set_exception(ChanClosedError('chan closed'))

    def getlock(self) -> Optional[Lock]:
        return self._group.getlock()
    
    def discarded(self) -> bool:
        return self._group.done()


# case send / recv

class _CaseSend(Generic[T]):
    def __init__(self, chan: Chan[T], item: T):
        self.chan = chan
        self.item = item


class _CaseRecv(Generic[T]):
    def __init__(self, chan: Chan[T]):
        self.chan = chan
        

# Chan

_empty_deque = deque(maxlen=0)

class Chan(Generic[T]):
    def __init__(self, buffsize: int = 0):
        self._buffsize = buffsize
        self._buff: Deque[T] = deque() if self._buffsize > 0 else _empty_deque
        self._readers: LinkedList[_ChanItemReader[T]] = LinkedList()
        self._writers: LinkedList[_ChanItemWriter[T]] = LinkedList()
        self._closed = False
        self._lock = Lock()


    def close(self):
        with self._lock:
            self._closed = True
            # close all readers
            while self._readers:
                reader = self._readers.popleft()
                lock = reader.getlock()
                if lock:
                    lock.acquire()
                try:
                    # close reader
                    if not reader.discarded():
                        reader.close()
                finally:
                    if lock:
                        lock.release()
            # close all writers
            while self._writers:
                writer = self._writers.popleft()
                lock = writer.getlock()
                if lock:
                    lock.acquire()
                try:
                    # close writer
                    if not writer.discarded():
                        writer.close()
                finally:
                    if lock:
                        lock.release()


    async def send(self, item: T):
        with self._lock:
            sent = self._send_inner(item)
            if sent:
                return

            writer = _SimpleChanItemWriter(item)
            self._writers.append(writer)
            
        await writer.write()


    async def recv(self) -> Tuple[Optional[T], bool]:
        with self._lock:
            received, item, ok = self._recv_inner()
            if received:
                return item, ok

            reader = _SimpleChanItemReader[T]()
            self._readers.append(reader)
            
        return await reader.read()


    def case_send(self, item: T) -> _CaseSend[T]:
        return _CaseSend(self, item)


    def case_recv(self) -> _CaseRecv[T]:
        return _CaseRecv(self)


    def send_nowait(self, item: T) -> bool:
        with self._lock:
            return self._send_inner(item)


    def recv_nowait(self) -> Tuple[bool, Optional[T], bool]:
        with self._lock:
            return self._recv_inner()


    def _send_inner(self, item: T) -> bool:
        ''' return sent: bool
        '''
        if self._closed:
            raise ChanClosedError('chan closed')

        while self._readers:
            reader = self._readers.popleft()
            lock = reader.getlock()
            if lock:
                lock.acquire()
            try:
                if not reader.discarded():
                    # send
                    reader.put(item, True)
                    return True
            finally:
                if lock:
                    lock.release()

        if len(self._buff) < self._buffsize:
            # send
            self._buff.append(item)
            return True
        
        return False


    def _recv_inner(self) -> Tuple[bool, Optional[T], bool]:
        ''' return (received, item, ok)
        '''
        if self._closed:
            if self._buff:
                item = self._buff.popleft()
                return True, item, True
            else:
                return True, None, False
            
        while self._writers:
            writer = self._writers.popleft()
            lock = writer.getlock()
            if lock:
                lock.acquire()
            try:
                if not writer.discarded():
                    # recv
                    item = writer.take()
                    if self._buff:
                        temp = item
                        item = self._buff.popleft()
                        self._buff.append(temp)
                    return True, item, True
            finally:
                if lock:
                    lock.release()
        
        if self._buff:
            # recv
            item = self._buff.popleft()
            return True, item, True
            
        return False, None, False


    def _send_with_mutex(self, item: T, group: _MutexGroup, id: int):
        if group.done():
            return
        
        with self._lock:
            if self._closed:
                raise ChanClosedError('chan closed')

            for rnode in self._readers.iternodes():
                reader = rnode.val
                lock_g = group.getlock()
                lock_r = reader.getlock()
                if lock_g is lock_r:
                    # one mutex group, just skip
                    continue
                with _GeminiLock(lock_g, lock_r) if lock_r else lock_g:
                    if group.done():
                        return
                    # delete node anyway
                    rnode.delete()
                    if reader.discarded():
                        continue
                    # both ready
                    reader.put(item, True)
                    group.set_result(id, item, True)
                    return

            if len(self._buff) < self._buffsize:
                with group.getlock():
                    if not group.done():
                        self._buff.append(item)
                        group.set_result(id, item, True)
                return
            
            writer = _MutexChanItemWriter(id, item, group)
            node = self._writers.append(writer)
            group.add_node(node, self)
    
    
    def _recv_with_mutex(self, group: _MutexGroup, id: int):
        if group.done():
            return
        
        with self._lock:
            if self._closed:
                # close the group as reader
                with group.getlock():
                    if not group.done():
                        if self._buff:
                            item = self._buff.popleft()
                            group.set_result(id, item, True)
                        else:
                            group.set_result(id, None, False)
                return
            
            for wnode in self._writers.iternodes():
                writer = wnode.val
                lock_g = group.getlock()
                lock_w = writer.getlock()
                if lock_g is lock_w:
                    # one mutex group, just skip
                    continue
                with _GeminiLock(lock_g, lock_w) if lock_w else lock_g:
                    if group.done():
                        return
                    # delete node anyway
                    wnode.delete()
                    if writer.discarded():
                        continue
                    # both ready
                    item = writer.take()
                    if self._buff:
                        temp = item
                        item = self._buff.popleft()
                        self._buff.append(temp)
                    group.set_result(id, item, True)
                    return
            
            if self._buff:
                with group.getlock():
                    if not group.done():
                        item = self._buff.popleft()
                        group.set_result(id, item, True)
                return
            
            reader = _MutexChanItemReader(id, group)
            node = self._readers.append(reader)
            group.add_node(node, self)


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
        fut: asyncio.Future[Tuple[Optional[T], bool]] = asyncio.Future()
        return await fut

    def send_nowait(self, item: T) -> bool:
        return False

    def recv_nowait(self) -> Tuple[bool, Optional[T], bool]:
        return False, None, False

    def _send_with_mutex(self, item: T, group: _MutexGroup, id: int):
        return
    
    def _recv_with_mutex(self, group: _MutexGroup, id: int):
        return


nilchan = _NilChan()


async def select(*ops: Union[Chan[Any], _CaseRecv[Any], _CaseSend[Any]], default: bool = False) -> Tuple[int, Any, bool]:
    closedError: Optional[ChanClosedError] = None
    if default:
        for id, op in enumerate(ops):
            if isinstance(op, Chan):
                success, item, ok = op.recv_nowait()
                if success:
                    return id, item, ok
            elif isinstance(op, _CaseRecv):
                success, item, ok = op.chan.recv_nowait()
                if success:
                    return id, item, ok
            elif isinstance(op, _CaseSend):
                try:
                    success = op.chan.send_nowait(op.item)
                    if success:
                        return id, op.item, True
                except ChanClosedError as ex:
                    closedError = ex
            else:
                raise TypeError(f'unsupported case type {type(op)} for select')
        
        if closedError:
            raise closedError
        else:
            return -1, None, False
    
    else:
        group = _MutexGroup()
        try:
            for id, op in enumerate(ops):
                if isinstance(op, Chan):
                    op._recv_with_mutex(group, id)
                elif isinstance(op, _CaseRecv):
                    op.chan._recv_with_mutex(group, id)
                elif isinstance(op, _CaseSend):
                    try:
                        op.chan._send_with_mutex(op.item, group, id)
                    except ChanClosedError as ex:
                        closedError = ex
                else:
                    raise TypeError(f'unsupported case type {type(op)} for select')

            if closedError and not group.done():
                with group.getlock():
                    if not group.done():
                        group.set_exception(closedError)
            
            return await group._future
        
        finally:
            group.release()
