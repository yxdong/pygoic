# pygoic

**pygoic** is a Go-like asynchronous concurrency library for python based on asyncio.

[![Supported Versions](https://img.shields.io/pypi/pyversions/pygoic.svg)](https://pypi.org/project/pygoic)

```python
import asyncio
from pygoic import go, do, Chan

ch = Chan()                     # chan without buff

async def foo1():
    await ch.send('hi')         # wait until received in foo2
    print('foo1: 0')
    await ch.send('a')
    await ch.send('b')
    ch.close()
    
async def foo2():
    await asyncio.sleep(0.01)
    print('foo2: 0')
    await ch.recv()             # gives ('hi', True)
    async for x in ch:          # loop until chan is closed and empty
        print(f'foo2: {x}')
    print('foo2: 1')

go(foo1())
do(foo2())                      # block until foo2 done

### Output ###
# foo2: 0
# foo1: 0
# foo2: a
# foo2: b
# foo2: 1

```

pygoic allows you to levarage coroutine in python extremely easily. There's no need to manually deal with trival and error-prone details, especially about event loop, which is designed to be so anti-human. This library will try its best to help you forgot those unpleasant things.

Follow a few simple principles, and you will get a Go-like concurrent programming experience. 


## Principles

1. Don't call any **blocking** operation inside coroutines. If not avoidable, please use `delegate`.
2. Function `do` can only be called out of coroutines, while `go` is for anywhere.


## Installation

```console
$ pip install pygoic
```


## Quick Tutorial

### go and do

`go` accepts a coroutine object (call of async funcion) as parameter, and start executing it concurrently (not accurate). You can expect `go` to behave the same as in Golang. Except it will return an `awaitable`, which can be used with `await` or `do` when need to wait.

`do` also accepts a coroutine object as parameter. The difference is that it will **block** until coroutine object is finished, and will return the result.

```python
import asyncio
from pygoic import go, do

async def foo1(t):
    await asyncio.sleep(0.01)
    print(f'foo1: {t}')
    return 'hello'
    
async def foo2():
    x = go(foo1(2))
    print('foo2')
    print(await x)
    return 'world'
    
go(foo1(1))
print(do(foo2()))

### Output ###
# foo2
# foo1: 1
# foo1: 2
# hello
# world

```

### delegate

`delegate` accepts a function and the args to call this function. It will execute this funcion in a thread pool, and return an `awaitable`. Looks like it is an asynchronous operation.

```python
import time
from pygoic import  go, do, delegate

async def foo1():
    await delegate(time.sleep, 0.02) 
    print('foo1')
    
async def foo2():
    await delegate(time.sleep, 0.01) 
    print('foo2')
    
x = go(foo1())
go(foo2())
do(x)

### Output ###
# foo2
# foo1

```

### Chan and select

Behavior of `Chan` is similar to that in Golang. 

`select` accepts `Chan`s as parameters, and returns when any of the `Chan` operations is unblocked. 

```python
from pygoic import Chan, select, go, do

ch1 = Chan()
ch2 = Chan()

async def foo1():
    await ch1.send('hi')
    print('foo1: 0')
    await ch2.send('a')
    await ch2.send('b')
    ch2.close()

async def foo2():
    id, item, ok = await select(ch1, ch2)
    if id == 0:
        print(f'foo2: 0, ch1')
    elif id == 1:
        print(f'foo2: 0, ch2')

    async for item in ch2:
        print(f'foo2: 1, {item}')

    print('foo2: 2')
    
go(foo1())
do(foo2())

### Output ###
# foo2: 0, ch1
# foo1: 0
# foo2: 1, a
# foo2: 1, b
# foo2: 2

```

### Context

You can expect `Context` to behave the same as in Golang.

```python
import asyncio
from pygoic import select, go, do
from pygoic import Background, WithCancel, WithTimeout, WithValue

ctx1 = WithValue(Background(), 'k', 'v')
ctx2, _ = WithTimeout(ctx1, 0.01)
ctx3, cancel = WithCancel(ctx2)

async def foo1():
    await asyncio.sleep(0.02)
    cancel()
    
async def foo2():
    print(ctx3.value('k'))
    go(foo1())
    
    id, item, ok = await select(ctx2.done(), ctx3.done())
    if id == 0:
        print('foo2: ctx2')
    elif id == 1:
        print('foo2: ctx3')
    
go(foo1())
go(foo2())
do(ctx3.done().recv())

### Output ###
# v
# foo2: ctx2

```

### After, AfterFunc and Timer

Behave the same as in Golang.

```python
from pygoic import go, do, select, Chan
from pygoic import After, AfterFunc

ch = Chan()

async def foo1():
    ch.close()
    
async def foo2():
    AfterFunc(0.015, foo1)
    id, item, ok = await select(After(0.01), ch)
    if id == 0:
        print('foo2: after')
    elif id == 1:
        print('foo2: ch')

    id, item, ok = await select(After(0.01), ch)
    if id == 0:
        print('foo2: after')
    elif id == 1:
        print('foo2: ch')

do(foo2())

### Output ###
# foo2: after
# foo2: ch

```

### WaitGroup

Behave the same as in Golang.

```python
import asyncio
from pygoic import go, do, WaitGroup

wg = WaitGroup(2)

async def foo1():
    wg.done()
    await asyncio.sleep(0.01)
    print('foo1: 0')
    wg.done()
    await asyncio.sleep(0.01)
    print('foo1: 1')
    
async def foo2():
    print('foo2: 0')
    await wg.wait()
    print('foo2: 1')

go(foo2())
do(foo1())

### Output ###
# foo2: 0
# foo1: 0
# foo2: 1
# foo1: 1

```
