

from abc import ABC, abstractmethod
from typing import Any, Hashable, Optional
import threading
from .channel import Chan




    
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
    def __init__(self):
        self._done = Chan[None]()
    
    def deadline(self) -> Optional[float]:
        return None
    
    def done(self) -> Chan[None]:
        return self._done
        
    def err(self) -> Optional[Exception]:
        return None
    
    def value(self, key: Hashable) -> Any:
        return None    


_background = _EmptyCtx()
_todo = _EmptyCtx()


def Background() -> Context:
    return _background


def TODO() -> Context:
    return _todo




class ContextCanceled(Exception):
    pass


class CancelFunc:
    pass


class CancelContext(Context):
    def __init__(self, parent: Context):
        self._parent = parent
        self._lock = threading.Lock()
        self._done: Optional[Chan[None]] = None
        self._children = set[CancelFunc]()
        self._err: Optional[Exception] = None
        

    def deadline(self) -> Optional[float]:
        pass
    

    def done(self) -> Chan[None]:
        pass
    

    def err(self) -> Optional[Exception]:
        pass
    

    def value(self, key: Hashable) -> Any:
        pass
            
    
        
        
    
        
    
    
    
    
