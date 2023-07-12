

import threading
from abc import ABC, abstractmethod
from typing import Any, Hashable, Optional, Tuple
from .channel import _NilChan, Chan

    
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
    def value(self, key: Hashable) -> Any:
        pass
    
    
class _EmptyCtx(Context):
    def deadline(self) -> Optional[float]:
        return None
    
    def done(self) -> Chan[None]:
        return _nil_chan
        
    def err(self) -> Optional[Exception]:
        return None
    
    def value(self, key: Hashable) -> Any:
        return None


_background = _EmptyCtx()
_todo = _EmptyCtx()

# closedchan is a reusable closed channel.
_closed_chan = Chan[None]()
_closed_chan.close()

_nil_chan = _NilChan[None]()
_cancel_ctx_key = object()


def Background() -> Context:
    return _background


def TODO() -> Context:
    return _todo




class ContextCanceled(Exception):
    pass


class ContextDeadlineExceededError(Exception):
    pass


class CancelFunc:
    pass


class _Canceler(ABC):
    @abstractmethod
    def _cancel(self, remove_from_parent: bool, err: Exception, cause: Exception):
        pass

    @abstractmethod
    def done(self) -> Chan[None]:
        pass





class CancelContext(Context, _Canceler):
    def __init__(self, context: Context):
        self.context = context
        self._lock = threading.Lock()
        self._done: Optional[Chan[None]] = None
        self._children = set[_Canceler]()
        self._err: Optional[Exception] = None
        self._cause: Optional[Exception] = None
        

    def deadline(self) -> Optional[float]:
        pass
    

    def done(self) -> Chan[None]:
        if self._done is not None:
            return self._done
        with self._lock:
            if self._done is None:
                self._done = Chan[None]()
            return self._done
    

    def err(self) -> Optional[Exception]:
        return self._err
    

    def value(self, key: Hashable) -> Any:
        if key == _cancel_ctx_key:
            return self
        return self.context.value(key)
            
    
    def _cancel(self, remove_from_parent: bool, err: Exception, cause: Exception):
        assert err is not None
        if cause is None:
            cause = err

        with self._lock:
            if self._err is not None:
                return
            
            self._err = err
            self._cause = cause
            if self._done is None:
                self._done = _closed_chan
            else:
                self._done.close()
            
            for child in self._children:
                child._cancel(False, err, cause)
            
            self._children.clear()

        if remove_from_parent:
            self.context.remove_child(self)

    
        
    
    
def _parent_cancel_ctx(parent: Context) -> Tuple[CancelContext, bool]:
    done = parent.done()
    
    
