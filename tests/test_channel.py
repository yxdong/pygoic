
import asyncio
from typing import List
from pygoroutine import go, do, delegate
from pygoroutine.channel import Chan, nilchan, select


def test_chan_send_buff():
    L: List[str] = []
    ch = Chan[str](1)
    done = Chan()
    
    async def f1():
        await ch.send('f1_0')
        L.append('f1_0')
        await ch.send('f1_1')
        L.append('f1_1')
        
    async def f2():
        await asyncio.sleep(0.001)
        L.append('f2_0')
        r, ok = await ch.recv()
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
    

