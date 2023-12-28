
import asyncio
from typing import List
from pygoic import go, do
from pygoic import Chan, nilchan, select, After
from pygoic import ChanClosedError


def test_chan_send_with_buff():
    L: List[str] = []
    ch = Chan[str](1)
    done = Chan()
    
    async def f1():
        # won't block
        await ch.send('f1_0')
        L.append('f1_0')
        # block until recived once
        await ch.send('f1_1')
        L.append('f1_1')
        
    async def f2():
        await asyncio.sleep(0.001)
        L.append('f2_0')
        r, ok = await ch.recv()  # unblock 'f1_1'
        assert r == 'f1_0' and ok
        await asyncio.sleep(0.001)
        L.append('f2_1')
        r, ok = await ch.recv()
        assert r == 'f1_1' and ok
        done.close()

    go(f1())
    go(f2())
    do(done.recv())
    assert L == ['f1_0', 'f2_0', 'f1_1', 'f2_1']
    

def test_chain_for_loop():
    L: List[str] = []
    ch = Chan[str]()
    done = Chan()

    async def f1():
        async for x in ch:
            L.append(x)
        L.append('f1_0')
        done.close()

    async def f2():
        await ch.send('f2_0')
        await ch.send('f2_1')
        await ch.send('f2_2')
        ch.close()

    go(f1())
    go(f2())
    do(done.recv())
    assert L == ['f2_0', 'f2_1', 'f2_2', 'f1_0']
    

def test_chan_recv_closed():
    L = []
    ch = Chan[str]()
    done = Chan()

    async def f1():
        x, _ = await ch.recv()
        L.append(x)
        x, _ = await ch.recv()
        L.append(x)
        L.append('f1_0')
        done.close()

    async def f2():
        await ch.send('f2_0')
        ch.close()

    go(f1())
    go(f2())
    do(done.recv())
    assert L == ['f2_0', None, 'f1_0']


def test_chan_send_closed():
    L = []
    ch = Chan[str]()
    done = Chan()

    async def f1():
        await ch.send('f1_0')
        try:
            await ch.send('f1_1')
        except:
            L.append('f1_2')
        else:
            L.append('f1_3')
        done.close()
        
    async def f2():
        x, ok = await ch.recv()
        L.append(x)
        ch.close()

    go(f1())
    go(f2())
    do(done.recv())
    assert L == ['f1_0', 'f1_2']


def test_select_basic():
    ch1 = Chan[str]()
    ch2 = Chan[str]()

    async def f1():
        await asyncio.sleep(0.001)
        await ch1.send('f1_0')

    async def f2():
        await asyncio.sleep(0.002)
        await ch2.send('f2_0')

    async def f3():
        id, x, ok = await select(ch1, ch2)
        assert id == 0
        assert x == 'f1_0'
        id, x, ok = await select(ch1, ch2)
        assert id == 1
        assert x == 'f2_0'

    go(f1())
    go(f2())
    do(f3())


def test_select_default():
    ch1 = Chan[str]()
    
    async def f1():
        return await select(ch1, default=True)
        
    id, x, ok = do(f1())
    assert id == -1
    assert x == None
    assert ok == False
    
    go(ch1.send(''))
    id, x, ok = do(f1())
    assert id == 0
    assert x == ''
    assert ok == True
    
    ch1.close()
    id, x, ok = do(f1())
    assert id == 0
    assert x == None
    assert ok == False
    

def test_select_send_recv():
    ch1 = Chan[str]()
    ch2 = Chan[str]()
    
    async def f1():
        return await select(ch1, ch1.case_send('1'))
    
    async def f2():
        return await select(ch2, ch2.case_send('2'), After(0.01))
    
    go(ch1.send('3'))
    id, x, ok = do(f1())
    assert id == 0
    assert x == '3'
    assert ok == True

    go(f1())
    x, ok = do(ch1.recv())
    assert x == '1'
    assert ok

    fut = go(f1())
    do(ch1.send('4'))
    id, x, ok = do(fut)
    assert id == 0
    assert x == '4'
    assert ok == True

    go(ch1.recv())
    id, x, ok = do(f1())
    assert id == 1
    assert x == '1'
    assert ok == True

    id, x, ok = do(f2())
    assert id == 2
    assert ok == True


def test_select_read_write_cross_1():
    ch1 = Chan[str]()
    ch2 = Chan[str]()
    
    async def f1():
        return await select(ch1.case_recv(), ch2.case_recv())
    
    async def f2():
        return await select(ch1.case_send('1'), ch2.case_send('2'))
    
    fut = go(f1())
    id2, x2, ok2 = do(f2())
    id1, x1, ok1 = do(fut)
    assert id1 == id2
    assert x1 == x2
    assert ok1 == ok2


def test_select_read_write_cross_2():
    ch = Chan[str]()

    async def f1():
        return await select(ch.case_recv(), ch.case_send('1'))
    
    async def f2():
        return await select(ch.case_recv(), ch.case_send('2'))
    
    fut = go(f1())
    id2, x2, ok2 = do(f2())
    id1, x1, ok1 = do(fut)
    
    assert id1 + id2 == 1
    assert x1 == x2
    assert ok1 and ok2


def test_select_write_closed_avoid():
    ch1 = Chan[str]()
    ch2 = Chan[str]()
    ch3 = Chan[str]()
    
    async def f1():
        ch1.close()
        id, x, ok = await select(ch1.case_send('1'), ch1.case_recv())
        assert id == 1
        assert x == None
        assert ok == False
        
        id, x, ok = await select(ch1.case_recv(), ch1.case_send('1'))
        assert id == 0
        assert x == None
        assert ok == False
        
        
    async def f_close_delay(ch: Chan[str]):
        await asyncio.sleep(0.01)
        ch.close()

    async def f2():
        go(f_close_delay(ch2))
        id, x, ok = await select(ch2.case_send('2'), ch2.case_recv())
        assert id == 1
        assert x == None
        assert ok == False
        
    async def f3():
        go(f_close_delay(ch3))
        id, x, ok = await select(ch3.case_recv(), ch3.case_send('3'))
        assert id == 0
        assert x == None
        assert ok == False
        
    do(asyncio.gather(
        go(f1()), 
        go(f2()), 
        go(f3()),
    ))


def test_write_closed():
    ch0 = Chan[str]()
    ch1 = Chan[str]()
    ch2 = Chan[str]()
    ch3 = Chan[str]()
    
    async def f1():
        ch1.close()
        try:
            await ch1.send('1')
        except ChanClosedError:
            pass
        else:
            assert False
    
    async def f2():
        ch2.close()
        try:
            await select(ch0.case_recv(), ch2.case_send('2'))
        except ChanClosedError:
            pass
        else:
            assert False
            
        try:
            await select(ch0.case_recv(), ch2.case_send('2'), default=True)
        except ChanClosedError:
            pass
        else:
            assert False

    async def f_close_delay(ch: Chan[str]):
        await asyncio.sleep(0.01)
        ch.close()
        
    async def f3():
        go(f_close_delay(ch3))
        try:
            await select(ch0.case_recv(), ch3.case_send('3'))
        except ChanClosedError:
            pass
        else:
            assert False
        
    do(asyncio.gather(
        go(f1()), 
        go(f2()), 
        go(f3()),
    ))
    

def test_nilchan():
    ch = Chan[str]()

    async def f1():
        id, x, ok = await select(ch, nilchan)
        assert id == 0
    
    ch.close()
    do(f1())
    
    try:
        nilchan.close()
    except:
        pass
    else:
        assert False

