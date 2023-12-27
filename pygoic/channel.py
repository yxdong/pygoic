
from __future__ import annotations
from abc import ABC, abstractmethod
import asyncio
from asyncio import Future
from collections import deque
import random
import threading
from typing import Any, Generic, List, Optional, Tuple, TypeVar, Deque, Union
from .linked import LinkedList, LinkedNode


T = TypeVar('T')


# exceptions

class ChanClosedError(Exception):
    pass


# abstract of chan item reader / writer

class _ChanItemReader(ABC, Generic[T]):
    @abstractmethod
    def put(self, item: T, ok: bool) -> bool:
        pass
    
    @abstractmethod
    def close(self):
        pass


class _ChanItemWriter(ABC, Generic[T]):
    @abstractmethod
    def take(self) -> Tuple[Optional[T], bool]:
        pass
    
    @abstractmethod
    def close(self):
        pass


# simple chan item reader / writer

class _SimpleChanItemReader(_ChanItemReader[T]):
    def __init__(self):
        self._future: asyncio.Future[Tuple[Optional[T], bool]] = asyncio.Future()
    
    def put(self, item: T, ok: bool) -> bool:
        self._future.set_result((item, ok))
        return True

    def close(self):
        self._future.set_result((None, False))
        

class _SimpleChanItemWriter(_ChanItemWriter[T]):
    def __init__(self, item: T):
        self._item = item
        self._future: asyncio.Future[None] = asyncio.Future()
    
    def take(self) -> Tuple[Optional[T], bool]:
        self._future.set_result(None)
        return self._item, True

    def close(self):
        self._future.set_exception(ChanClosedError('chan closed'))


# mutex reader / writer group

class _MutexGroup:
    def __init__(self):
        self._future: asyncio.Future[Tuple[int, Any, bool]] = asyncio.Future()
        self._lock = threading.Lock()
        self._reader_nodes: List[Tuple[Chan, LinkedNode]] = []
        self._writer_nodes: List[Tuple[Chan, LinkedNode]] = []

    def set_result(self, id: int, item: Any, ok: bool) -> bool:
        with self._lock:
            if self._future.done():
                return False
            self._future.set_result((id, item, ok))
            return True

    def set_exception(self, ex: Exception) -> bool:
        with self._lock:
            if self._future.done():
                return False
            self._future.set_exception(ex)
            return True

    def is_reader_mutex(self, reader: _ChanItemReader) -> bool:
        if isinstance(reader, _MutexChanItemReader):
            return reader._group is self
        else:
            return False

    def is_writer_mutex(self, writer: _ChanItemWriter) -> bool:
        if isinstance(writer, _MutexChanItemWriter):
            return writer._group is self
        else:
            return False

    def release(self):
        for chan, node in self._reader_nodes:
            chan._remove_reader_node(node)
        for chan, node in self._writer_nodes:
            chan._remove_writer_node(node)


class _MutexChanItemReader(_ChanItemReader[T]):
    def __init__(self, id: int, group: _MutexGroup):
        self._id = id
        self._group = group
    
    def put(self, item: T, ok: bool) -> bool:
        return self._group.set_result(self._id, item, ok)

    def close(self):
        self._group.set_result(self._id, None, False)


class _MutexChanItemWriter(_ChanItemWriter[T]):
    def __init__(self, id: int, item: T, group: _MutexGroup):
        self._id = id
        self._item = item
        self._group = group
    
    def take(self) -> Tuple[Optional[T], bool]:
        if self._group.set_result(self._id, self._item, True):
            return self._item, True
        else:
            return None, False

    def close(self):
        self._group.set_exception(ChanClosedError('chan closed'))



class Chan(Generic[T]):
    def __init__(self, buffsize: int = 0):
        self._buffsize = buffsize
        self._buff: Deque[T] = deque()
        self._readers: LinkedList[_ChanItemReader[T]] = LinkedList()
        self._writers: LinkedList[_ChanItemWriter[T]] = LinkedList()
        self._closed = False
        self._lock = threading.Lock()


    def close(self):
        with self._lock:
            self._closed = True
            while self._writers:
                writer = self._writers.popleft()
                writer.close()
            while self._readers:
                reader = self._readers.popleft()
                reader.close()


    async def send(self, item: T):
        with self._lock:
            sent = self._send_inner(item)
            if sent:
                return

            writer = _SimpleChanItemWriter(item)
            self._writers.append(writer)
            
        await writer._future


    async def recv(self) -> Tuple[Optional[T], bool]:
        with self._lock:
            received, item, ok = self._recv_inner()
            if received:
                return item, ok

            reader = _SimpleChanItemReader[T]()
            self._readers.append(reader)
            
        return await reader._future


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
            if reader.put(item, True):
                return True

        if len(self._buff) < self._buffsize:
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
            item, ok = writer.take()
            if ok:
                if self._buff:
                    ret = self._buff.popleft()
                    self._buff.append(item) # type: ignore
                    return True, ret, True
                else:
                    return True, item, True
        
        if self._buff:
            item = self._buff.popleft()
            return True, item, True
            
        return False, None, False


    def _send_with_mutex(self, item: T, id: int, group: _MutexGroup):
        with self._lock, group._lock:
            if group._future.done():
                return
            
            if self._closed:
                group._future.set_exception(ChanClosedError('chan closed'))
                return

            for rnode in self._readers.iternodes():
                reader = rnode.val
                if group.is_reader_mutex(reader):
                    continue
                self._readers.remove(rnode)
                if reader.put(item, True):
                    group._future.set_result((id, item, True))
                    return

            if len(self._buff) < self._buffsize:
                self._buff.append(item)
                group._future.set_result((id, item, True))
                return 
            
            writer = _MutexChanItemWriter(id, item, group)
            node = self._writers.append(writer)
            group._writer_nodes.append((self, node))
    
    
    def _recv_with_mutex(self, id: int, group: _MutexGroup):
        with self._lock, group._lock:
            if group._future.done():
                return
            
            if self._closed:
                if self._buff:
                    item = self._buff.popleft()
                    group._future.set_result((id, item, True))
                    return
                else:
                    group._future.set_result((id, None, False))
                    return
            
            for wnode in self._writers.iternodes():
                writer = wnode.val
                if group.is_writer_mutex(writer):
                    continue
                self._writers.remove(wnode)
                item, ok = writer.take()
                if ok:
                    if self._buff:
                        ret = self._buff.popleft()
                        self._buff.append(item) # type: ignore
                        group._future.set_result((id, ret, True))
                        return
                    else:
                        group._future.set_result((id, item, True))
                        return
            
            if self._buff:
                item = self._buff.popleft()
                group._future.set_result((id, item, True))
                return
            
            reader = _MutexChanItemReader(id, group)
            node = self._readers.append(reader)
            group._reader_nodes.append((self, node))


    def _remove_writer_node(self, node: LinkedNode):
        with self._lock:
            self._writers.remove(node)
    
    
    def _remove_reader_node(self, node: LinkedNode):
        with self._lock:
            self._readers.remove(node)    


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

    def _send_with_mutex(self, item: T, id: int, group: _MutexGroup):
        return
    
    def _recv_with_mutex(self, id: int, group: _MutexGroup):
        return
    
    def _remove_writer_node(self, node: LinkedNode):
        return

    def _remove_reader_node(self, node: LinkedNode):
        return


nilchan = _NilChan()


async def select(*ops: Union[Chan[Any], Tuple[Chan[Any], Any]], default: bool = False) -> Tuple[int, Any, bool]:
    shuffled = list(enumerate(ops))
    random.shuffle(shuffled)

    if default:
        for i, op in shuffled:
            if isinstance(op, Chan):
                success, item, ok = op.recv_nowait()
                if success:
                    return i, item, ok
            else:
                chan, item = op
                success = chan.send_nowait(item)
                if success:
                    return i, item, True
                
        return -1, None, False

    else:
        group = _MutexGroup()
        try:
            for i, op in shuffled:
                if isinstance(op, Chan):
                    op._recv_with_mutex(i, group)
                else:
                    chan, item = op
                    chan._send_with_mutex(item, i, group)
                
            return await group._future
        finally:
            group.release()
