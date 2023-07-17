
import asyncio
from typing import List
from pygoic import go, do, delegate
from pygoic.channel import Chan, nilchan, select


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


def test_select():
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

    go(f1())
    go(f2())
    do(f3())


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

