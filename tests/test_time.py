

import asyncio
from pygoroutine import go, do
from pygoroutine.channel import select, Chan
from pygoroutine.context import Background, WithCancel
from pygoroutine.time import After, AfterFunc


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

