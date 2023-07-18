
import threading
import time
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar

from .channel import Chan
from .executor import _get_event_loop, go


T = TypeVar('T')


class _Value(Generic[T]):
    def __init__(self, val: T):
        self._val = val

    def get(self) -> T:
        return self._val
    
    def set(self, val: T):
        self._val = val


class Timer:
    def __init__(self, duration: float, func: Optional[Callable[[], Any]] = None):
        self.C = Chan[float](1)
        self._active: _Value[bool] = _Value(True)
        self._lock = threading.Lock()
        self._func: Callable[[], Any]
        if func is None:
            self._func = self._send_time
        else:
            self._func = func

        self._timer = _get_event_loop().call_later(
            duration,
            self._callback,
            self._active,
        )


    def stop(self) -> bool:
        with self._lock:
            if self._active.get():
                self._active.set(False)
                self._timer.cancel()
                return True
            else:
                return False


    def reset(self, duration: float) -> bool:
        with self._lock:
            if self._active.get():
                self._active.set(False)
                self._timer.cancel()
                self._active = _Value(True)
                self._timer = _get_event_loop().call_later(
                    duration,
                    self._callback,
                    self._active,
                )
                return True
            else:
                self._active = _Value(True)
                self._timer = _get_event_loop().call_later(
                    duration,
                    self._callback,
                    self._active,
                )
                return False


    def _callback(self, active: _Value[bool]):
        with self._lock:
            if active.get():
                active.set(False)
                self._func()


    def _send_time(self):
        self.C.send_nowait(time.time())



def AfterFunc(duration: float, func: Callable[[], Awaitable[Any]]) -> Timer:
    def anonymous():
        go(func())
    return Timer(duration, anonymous)



def After(duration: float) -> Chan[float]:
	return Timer(duration).C


