


import asyncio
from collections import deque
from concurrent.futures import Future
import time
from typing import List
from pygoroutine import go, do
from pygoroutine.channel import Chan
from pygoroutine.executor import GoroutineExecutor, delegate


g = GoroutineExecutor()



async def _work_1(idx: int):
    print(f'start {idx}')
    #loop = asyncio.get_running_loop()
    #future = loop.create_future()
    future = asyncio.Future()
    go(_work_2(future))
    print(await future)
    print(f'end {idx}')


async def _work_2(future: Future):
    await asyncio.sleep(2)
    future.set_result('hello')


async def _work_3(idx: int):
    print(f'start {idx}')
    await asyncio.sleep(2)
    print(f'end {idx}')
    return 'hello'
    


def test_goroutine_basic():
    f = go(_work_1(3))
    f.result()





async def get_ff():
    g._loop.call_soon_threadsafe
    return asyncio.Future()


async def ff_wait(fut):
    x = await fut
    print(x)
    
    
async def ff_prod(fut):
    await asyncio.sleep(2)
    fut.set_result('hello')
    
    
async def kk(k):
    z = asyncio._get_running_loop()
    print(f'{z}')
    for i in range(100):
        print(k)

async def aa():
    return 'hello'

async def bb():
    x = aa()
    print(await x)
    
    
    
async def gloop():
    return asyncio._get_running_loop()


async def consume(idx, x: List[int]):
    while x:
        d = x.pop()
        print(f'{idx} {d}')




async def work_4():
    ff = []
    for i in range(5):
        f = go(_work_3(i))
        ff.append(f)
        
    #await asyncio.sleep(3)
    await delegate(time.sleep, 3)

    return 'world'


async def ch_work1(ch: Chan[str]):
    await asyncio.sleep(1)
    x, ok = await ch.recv()
    print(f'recv {x}')


async def ch_work2(ch: Chan[str]):
    await ch.send('hello')
    print('send done')

async def chan_test_main():
    ch = Chan[str]()
    f1 = go(ch_work1(ch))
    f2 = go(ch_work2(ch))
    await f1
    await f2


if __name__ == '__main__':
    '''
    ff = []
    for i in range(5):
        f = go(_work_3(i))
        ff.append(f)
        
    for f in ff:
        f.result()
        print(f.result())
    '''
    do(chan_test_main())
    

    
    
