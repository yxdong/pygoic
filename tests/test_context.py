

import time
from pygoic import go, do
from pygoic import Chan, nilchan
from pygoic import Background, Canceled, DeadlineExceeded, WithCancel, WithDeadline, WithTimeout, WithValue


def test_background():
    ctx = Background()
    assert ctx.deadline() is None
    assert ctx.err() is None
    assert ctx.done() is nilchan


def test_cancel():
    ctx1, cancel1 = WithCancel(Background())
    ctx2 = WithValue(ctx1, 'k', 'v')
    ctx3, _ = WithTimeout(ctx2, 0.1)
    ctx4, cancel4 = WithCancel(ctx3)
    ctx5 = WithValue(ctx4, 'k', 'v')

    async def f1():
        await ctx5.done().recv()
        assert ctx5.err() == Canceled
        assert ctx4.err() == Canceled
        assert ctx3.err() is None
        assert ctx2.err() is None
        assert ctx1.err() is None

        await ctx3.done().recv()
        assert ctx3.err() == Canceled
        assert ctx2.err() == Canceled
        assert ctx1.err() == Canceled

    x = go(f1())
    cancel4()
    time.sleep(0.001)
    cancel1()
    do(x)


def test_timeout():
    ctx0, _ = WithTimeout(Background(), 0)
    ctx1= WithValue(ctx0, 'k', 'v')
    _, ok1 = do(ctx1.done().recv())
    assert ctx0.err() is not None
    assert ctx1.err() is not None
    assert ok1 == False

    ctx2, _ = WithTimeout(Background(), 0.002)
    ctx3 = WithValue(ctx2, 'k', 'v')
    ctx4, _ = WithTimeout(ctx3, 0.001)
    ctx5 = WithValue(ctx4, 'k', 'v')
    assert ctx2.err() is None
    assert ctx3.err() is None
    assert ctx4.err() is None
    assert ctx5.err() is None

    async def f1():
        await ctx5.done().recv()
        assert ctx5.err() == DeadlineExceeded
        assert ctx4.err() == DeadlineExceeded
        assert ctx3.err() is None
        assert ctx2.err() is None

        await ctx3.done().recv()
        assert ctx5.err() == DeadlineExceeded
        assert ctx4.err() == DeadlineExceeded
        assert ctx3.err() == DeadlineExceeded
        assert ctx2.err() == DeadlineExceeded

    do(f1())


def test_deadline():
    ctx, cancel = WithDeadline(Background(), time.time() - 1)
    assert ctx.err() is not None

    ctx, cancel = WithDeadline(Background(), time.time())
    assert ctx.err() is not None

    ctx, cancel = WithDeadline(Background(), time.time() + 0.001)
    assert ctx.err() is None

    async def f1():
        await ctx.done().recv()
        assert ctx.err()

    do(f1())


def test_value():
    ctx1 = WithValue(Background(), 'k1', 'v1')
    ctx2 = WithValue(ctx1, 'k2', 'v2')
    ctx3 = WithValue(ctx2, 'k1', 'v3')

    assert ctx1.value('k1') == 'v1'
    assert ctx1.value('k2') == None
    assert ctx2.value('k1') == 'v1'
    assert ctx2.value('k2') == 'v2'
    assert ctx3.value('k1') == 'v3'
    assert ctx3.value('k2') == 'v2'

