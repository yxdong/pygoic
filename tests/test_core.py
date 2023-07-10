


import asyncio
from concurrent.futures import Future
import time
from typing import List
from pygoroutine import go, do




async def _work_1(idx: int) -> int:
    print(f'start {idx}')
    await asyncio.sleep(1)
    print(f'end {idx}')
    return 3



def test_goroutine_basic():
    x: Future[int] = go(_work_1(1))
    print(x.result())
        

