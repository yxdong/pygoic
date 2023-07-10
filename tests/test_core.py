


import asyncio
from concurrent.futures import Future
import time
from typing import List
from pygoroutine import go, do




async def _work_1(idx: int):
    print(f'start {idx}')
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    go(_work_2(future))
    await future
    print(f'end {idx}')


async def _work_2(future: Future):
    await asyncio.sleep(2)
    future.cancel()



def test_goroutine_basic():
    f = go(_work_1(3))
    f.result()


