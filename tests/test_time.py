

import asyncio
from pygoic import go, do
from pygoic import select, Chan
from pygoic import Background, WithCancel
from pygoic import After, AfterFunc, Timer


def test_after():
    async def f1():
        ctx, cancel = WithCancel(Background())
        async def anonymous():
            await asyncio.sleep(0.002)
            cancel()
        go(anonymous())
        id, x, ok = await select(After(0.001), ctx.done())
        assert id == 0

    async def f2():
        ctx, cancel = WithCancel(Background())
        async def anonymous():
            await asyncio.sleep(0.001)
            cancel()
        go(anonymous())
        id, x, ok = await select(After(0.002), ctx.done())
        assert id == 1

    x1 = go(f1())
    x2 = go(f2())
    do(x1)
    do(x2)


def test_after_func():
    done = Chan()
    async def f1():
        await done.send('f1_0')
    
    timer = AfterFunc(0.001, f1)
    x, ok = do(done.recv())
    assert x == 'f1_0'
    assert ok


def test_timer_stop():
    timer = Timer(0.001)
    async def f1():
        id, x, ok = await select(timer.C, After(0.002))
        assert id == 1
        
    x = go(f1())
    timer.stop()
    do(x)


def test_timer_reset_done():
    timer = Timer(0.001)
    async def f1():
        x, ok = await timer.C.recv()
        assert isinstance(x, float) and ok
        timer.reset(0.001)
        x, ok = await timer.C.recv()
        assert isinstance(x, float) and ok
        
    do(f1())


def test_timer_reset_waiting():
    timer = Timer(0.01)
    
    async def f1():
        await asyncio.sleep(0.001)
        timer.reset(0.001)
        
    async def f2():
        go(f1())
        id, x, ok = await select(timer.C, After(0.004))
        assert id == 0 and ok
        # make sure won't send twice
        id, x, ok = await select(timer.C, After(0.02))
        assert id == 1 and ok
        
    do(f2())
