

import asyncio
from asyncio import mixins
from collections import deque
from typing import Any, Generic, Optional, Tuple, TypeVar


T = TypeVar('T')

class Chan(Generic[T]):
    def __init__(self, buffsize: int = 0):
        assert buffsize >= 0
        self._buffsize = buffsize
        self._swap: Optional[T] = None

        # buffer
        if self._buffsize > 0:
            self._queue = deque[T]()
        else:
            self._queue = None

        # status
        self._bound = mixins._LoopBoundMixin(loop=mixins._marker)
        self._closed: bool = False




    def close(self):
        pass
        


    async def send(self, item: T):
        pass


    async def recv(self) -> Tuple[Optional[T], bool]:
        pass

    

async def select(*chans: Chan[Any]) -> Tuple[int, Any, bool]: 
    pass