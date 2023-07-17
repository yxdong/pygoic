


import asyncio
import time
from typing import List
from pygoroutine import go, do, delegate


def test_go_basic():
    do(delegate(lambda x: x, 1))
    L: List[str] = []
    
    async def f1():
        await asyncio.sleep(0.001)
        L.append('f1_0')
    
    go(f1())
    L.append('m_0')
    time.sleep(0.002)
    assert L == ['m_0', 'f1_0']
    

def test_do_basic():
    async def f1() -> str:
        await asyncio.sleep(0.001)
        return 'f1'
    
    r1 = do(f1())
    assert r1 == 'f1'


def test_delegate_basic():
    do(delegate(lambda x: x, 1))
    L: List[str] = []
    
    async def f1():
        await delegate(time.sleep, 0.001)
        L.append('f1_0')
        await delegate(time.sleep, 0.002)
        L.append('f1_1')
        
    async def f2():
        await asyncio.sleep(0.002)
        L.append('f2_0')
    
    go(f1())
    go(f2())
    L.append('m_0')
    time.sleep(0.005)
    L.append('m_1')
    assert L == ['m_0', 'f1_0', 'f2_0', 'f1_1', 'm_1']
    

def test_go_do_wrap():
    L: List[str] = []
    async def f1():
        await asyncio.sleep(0.001)
        L.append('f1_0')
        return 'f1'
        
    r = do(go(go(f1())))
    assert r == 'f1'
    assert L == ['f1_0']
        
        
def test_go_result():
    L: List[str] = []
    async def f1():
        await asyncio.sleep(0.001)
        L.append('f1_0')
        return 'f1'
    
    x = go(f1())
    r = x.result()
    assert r == 'f1'
    assert L == ['f1_0']
    

def test_go_await():
    L: List[str] = []
    
    async def f1():
        await asyncio.sleep(0.001)
        L.append('f1_0')
        return 'f1'
    
    async def f2():
        x = go(f1())
        L.append('f2_0')
        return await x
    
    r = do(f2())
    assert r == 'f1'
    assert L == ['f2_0', 'f1_0']
    

def test_do_in_coro_with_error():
    async def f1():
        pass
    async def f2():
        do(f1())
    try:
        do(f2())
    except:
        pass
    else:
        assert False


def test_go_result_in_coro_with_error():
    async def f1():
        pass
    async def f2():
        x = go(f1())
        x.result()

    try:
        do(f2())
    except:
        pass
    else:
        assert False

