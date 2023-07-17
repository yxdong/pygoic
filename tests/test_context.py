

import time
from pygoroutine import go, do
from pygoroutine.channel import Chan
from pygoroutine.context import Background, CanceledError, DeadlineExceededError, WithCancel, WithDeadline, WithTimeout, WithValue
from pygoroutine.context import nilchan


def test_background():
    ctx = Background()
    assert ctx.deadline() is None
    assert ctx.err() is None
    assert ctx.done() is nilchan


def test_cancel():
    done1 = Chan()
    done2 = Chan()
    ctx1, cancel1 = WithCancel(Background())
    ctx2 = WithValue(ctx1, 'k', 'v')
    ctx3, _ = WithTimeout(ctx2, 0.1)
    ctx4, cancel4 = WithCancel(ctx3)
    ctx5 = WithValue(ctx4, 'k', 'v')

    async def f1():
        await ctx5.done().recv()
        assert isinstance(ctx5.err(), CanceledError)
        assert isinstance(ctx4.err(), CanceledError)
        assert ctx3.err() is None
        assert ctx2.err() is None
        assert ctx1.err() is None

        done1.close()
        await ctx3.done().recv()
        assert isinstance(ctx3.err(), CanceledError)
        assert isinstance(ctx2.err(), CanceledError)
        assert isinstance(ctx1.err(), CanceledError)
        done2.close()

    go(f1())
    cancel4()
    do(done1.recv())
    cancel1()
    do(done2.recv())


def test_timeout():
    done = Chan()

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
        assert isinstance(ctx5.err(), DeadlineExceededError)
        assert isinstance(ctx4.err(), DeadlineExceededError)
        assert ctx3.err() is None
        assert ctx2.err() is None

        await ctx3.done().recv()
        assert isinstance(ctx5.err(), DeadlineExceededError)
        assert isinstance(ctx4.err(), DeadlineExceededError)
        assert isinstance(ctx3.err(), DeadlineExceededError)
        assert isinstance(ctx2.err(), DeadlineExceededError)
        
        done.close()

    go(f1())
    do(done.recv())


def test_deadline():
    done = Chan()
    
    ctx, cancel = WithDeadline(Background(), time.time() - 1)
    assert ctx.err() is not None

    ctx, cancel = WithDeadline(Background(), time.time())
    assert ctx.err() is not None

    ctx, cancel = WithDeadline(Background(), time.time() + 0.001)
    assert ctx.err() is None

    async def f1():
        await ctx.done().recv()
        assert ctx.err()
        done.close()

    go(f1())
    do(done.recv())


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


