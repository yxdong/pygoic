


import asyncio
import time
from pygoic import go, do, WaitGroup


def test_waitgroup_basic():
    L = []
    wg = WaitGroup(2)
    
    async def f1():
        L.append('f1_0')
        await wg.wait()
        L.append('f1_1')
        
    async def f2():
        await asyncio.sleep(0.001)
        L.append('f2_0')
        wg.done()
        await asyncio.sleep(0.001)
        L.append('f2_1')
        wg.done()
        await asyncio.sleep(0.001)
        L.append('f2_2')
        
    go(f1())
    go(f1())
    do(f2())
    assert L == ['f1_0', 'f1_0', 'f2_0', 'f2_1', 'f1_1', 'f1_1', 'f2_2']


def test_waitgroup_negative_state_error():
    try:
        WaitGroup(-1)
    except:
        pass
    else:
        assert False
        
    wg = WaitGroup()
    try:
        wg.done()
    except:
        pass
    else:
        assert False
        
        
def test_waitgroup_add_wait_error():
    wg = WaitGroup(1)
    
    async def f1():
        await wg.wait()
    
    go(f1())
    time.sleep(0.001)
    try:
        wg.add(1)
    except:
        pass
    else:
        assert False
    wg.done()


def test_waitgroup_reuse():
    L = []
    wg = WaitGroup(1)
    
    async def f1():
        L.append('f1_0')
        await wg.wait()
        L.append('f1_1')
        await wg.wait()
        L.append('f1_2')
    
    go(f1())
    time.sleep(0.001)
    L.append('m_0')
    wg.done()
    time.sleep(0.001)
    L.append('m_1')
    wg.add(1)
    L.append('m_2')
    go(f1())
    time.sleep(0.001)
    L.append('m_3')
    wg.done()
    time.sleep(0.001)
    L.append('m_4')
    assert L == ['f1_0', 'm_0', 'f1_1', 'f1_2', 'm_1', 'm_2', 'f1_0', 'm_3', 'f1_1', 'f1_2', 'm_4']
