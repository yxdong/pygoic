
from __future__ import annotations
import threading
from abc import ABC, abstractmethod
import time
from typing import Any, Callable, Optional, Set, Tuple
from .channel import Chan, nilchan, select
from .executor import go
from .time import AfterFunc, Timer


class Context(ABC):
    @abstractmethod
    def deadline(self) -> Optional[float]:
        pass
    
    @abstractmethod
    def done(self) -> Chan[None]:
        pass
    
    @abstractmethod
    def err(self) -> Optional[Exception]:
        pass
    
    @abstractmethod
    def value(self, key: Any) -> Any:
        pass
    

class CanceledError(Exception):
    pass


class DeadlineExceededError(Exception):
    pass


Canceled = CanceledError("context canceled")
DeadlineExceeded = DeadlineExceededError("context deadline exceeded")

    
class _EmptyCtx(Context):
    def deadline(self) -> Optional[float]:
        return None
    
    def done(self) -> Chan[None]:
        return nilchan
        
    def err(self) -> Optional[Exception]:
        return None
    
    def value(self, key: Any) -> Any:
        return None


_background = _EmptyCtx()
_todo = _EmptyCtx()


def Background() -> Context:
    return _background


def TODO() -> Context:
    return _todo


CancelFunc = Callable[[], Any]


def WithCancel(parent: Context) -> Tuple[Context, CancelFunc]:
    if parent is None:
        raise Exception("cannot create context from nil parent")
    
    c = _CancelCtx(parent)
    _propagate_cancel(parent, c)
    return c, lambda: c._cancel(True, Canceled)
        

class _Canceler(ABC):
    @abstractmethod
    def _cancel(self, remove_from_parent: bool, err: Exception):
        pass

    @abstractmethod
    def done(self) -> Chan[None]:
        pass


def _propagate_cancel(parent: Context, child: _Canceler):
    done = parent.done()
    if done == nilchan:
        # parent is never canceled
        return
    
    success, _, _ = done.recv_nowait()
    if success:
        # parent is already canceled
        child._cancel(False, parent.err()) # type: ignore
        return
    
    p, ok = _parent_cancel_ctx(parent)
    if ok:
        assert p is not None
        with p._lock:
            if p._err is not None:
                # parent has already been canceled
                child._cancel(False, p._err)
            else:
                p._children.add(child)
    else:
        async def anonymous():
            id, _, _ = await select(parent.done(), child.done())
            if id == 0:
                child._cancel(False, parent.err()) # type: ignore
    
        go(anonymous())
    

_cancel_ctx_key = object()


class _CancelCtx(Context, _Canceler):
    def __init__(self, context: Context):
        self._context = context
        self._lock = threading.Lock()
        self._done: Optional[Chan[None]] = None
        self._children: Set[_Canceler] = set()
        self._err: Optional[Exception] = None
        

    def deadline(self) -> Optional[float]:
        return self._context.deadline()
    

    def done(self) -> Chan[None]:
        if self._done is not None:
            return self._done
        with self._lock:
            if self._done is None:
                self._done = Chan[None]()
            return self._done
    

    def err(self) -> Optional[Exception]:
        return self._err
    

    def value(self, key: Any) -> Any:
        if key == _cancel_ctx_key:
            return self
        return _value(self._context, key)
            
    
    def _cancel(self, remove_from_parent: bool, err: Exception):
        if err is None:
            raise Exception('context: internal error: missing cancel error')

        with self._lock:
            if self._err is not None:
                return
            
            self._err = err
            if self._done is None:
                self._done = _closed_chan
            else:
                self._done.close()
            
            for child in self._children:
                child._cancel(False, err)
            
            self._children = set()

        if remove_from_parent:
            _remove_child(self._context, self)



def _parent_cancel_ctx(parent: Context) -> Tuple[Optional[_CancelCtx], bool]:
    done = parent.done()
    if done == _closed_chan or done == nilchan:
        return None, False
    
    p = parent.value(_cancel_ctx_key)
    if not isinstance(p, _CancelCtx):
        return None, False
    
    pdone = p._done
    if pdone != done:
        return None, False
    
    return p, True

    
def _remove_child(parent: Context, child: _Canceler):
    p, ok = _parent_cancel_ctx(parent)
    if not ok:
        return
    
    assert p is not None
    with p._lock:
        if child in p._children:
            p._children.remove(child)
    

# closedchan is a reusable closed channel.
_closed_chan = Chan[None]()
_closed_chan.close()


def WithDeadline(parent: Context, d: float) -> Tuple[Context, CancelFunc]:
    if parent is None:
        raise Exception("cannot create context from nil parent")
    
    cur = parent.deadline()
    if cur is not None and cur < d:
        # The current deadline is already sooner than the new one.
        return WithCancel(parent)
    
    c = _TimerCtx(_CancelCtx(parent), d)
    _propagate_cancel(parent, c)
    dur = d - time.time()
    if dur <= 0:
        c._cancel(True, DeadlineExceeded)
        return c, lambda: c._cancel(False, Canceled)
    
    with c._cancel_ctx._lock:
        if c._cancel_ctx._err is None:
            async def anomymous():
                c._cancel(True, DeadlineExceeded)

            c._timer = AfterFunc(
                dur, 
                anomymous,
            )
            
        return c, lambda: c._cancel(True, Canceled)


class _TimerCtx(Context, _Canceler):
    def __init__(self, cancel_ctx: _CancelCtx, deadline: float):
        self._cancel_ctx = cancel_ctx
        self._timer: Optional[Timer] = None
        self._deadline = deadline

    def deadline(self) -> Optional[float]:
        return self._deadline
    
    def done(self) -> Chan[None]:
        return self._cancel_ctx.done()
    
    def err(self) -> Optional[Exception]:
        return self._cancel_ctx.err()
    
    def value(self, key: Any) -> Any:
        return self._cancel_ctx.value(key)

    def _cancel(self, remove_from_parent: bool, err: Exception):
        self._cancel_ctx._cancel(False, err)
        if remove_from_parent:
            _remove_child(self._cancel_ctx._context, self)
        with self._cancel_ctx._lock:
            if self._timer is not None:
                self._timer.stop()
                self._timer = None


def WithTimeout(parent: Context, timeout: float) -> Tuple[Context, CancelFunc]:
    return WithDeadline(parent, time.time() + timeout)


def WithValue(parent: Context, key: Any, val: Any) -> Context:
    if parent is None:
        raise Exception("cannot create context from nil parent")
    if key is None:
        raise Exception("nil key")
    return _ValueCtx(parent, key, val)

    
class _ValueCtx(Context):
    def __init__(self, parent: Context, key: Any, val: Any):
        self._context = parent
        self._key = key
        self._val = val
        
    def deadline(self) -> Optional[float]:
        return self._context.deadline()
    
    def done(self) -> Chan[None]:
        return self._context.done()
    
    def err(self) -> Optional[Exception]:
        return self._context.err()
    
    def value(self, key: Any) -> Any:
        if self._key == key:
            return self._val
        return _value(self._context, key)
    
    
def _value(c: Context, key: Any) -> Any:
    while True:
        if isinstance(c, _ValueCtx):
            if key == c._key:
                return c._val
            c = c._context
            
        elif isinstance(c, _CancelCtx):
            if key == _cancel_ctx_key:
                return c
            c = c._context
        
        elif isinstance(c, _TimerCtx):
            if key == _cancel_ctx_key:
                return c._cancel_ctx
            c = c._cancel_ctx._context
            
        elif isinstance(c, _EmptyCtx):
            return None
        
        else:
            return c.value(key)


