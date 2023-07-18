# pygoic

**pygoic** is a simple, golang style, concurrency python library on asyncio.

```python
import asyncio
from pygoic import Chan, go, do
from pygoic import Background, WithCancel

ctx, cancel = WithCancel(Background())
ch = Chan()

async def foo1():
    await ch.send('hi')
    print('foo1')
    cancel()
    
async def foo2():
    await asyncio.sleep(0.01)
    print('foo2')
    await ch.recv()
    
async def foo3():
    await ctx.done().recv()
    print('foo3')
    
go(foo1())
go(foo2())
go(foo3())
do(ctx.done().recv())  # block until ctx done

### Output:
# foo2
# foo1
# foo3

```

pygoic allows you to levarage coroutine in python extremely easily. There's no need to manually deal with a lot of trival and error-prone details, especially about event loop, which is designed to be so anti-human. This library will try its best to help you forgot those unpleasant things.

Follow a few simple principles, and you will get a golang-like concurrent programming experience. 


## Principles
1. Do not call any **blocking** operation inside coroutines. If you can't avoid it, use `delegate`.  
    *Common blocking operations include but are not limited to:*
    * `requests.post`
    * `time.sleep`
    * `queue.Queue.get`
    * `threading.Lock.acquire`
2. `do` can only be called out of coroutines, while `go` is for anywhere.



## Installation

```console
$ python -m pip install pygoic
```

pygoic officially supports Python 3.8+.


## Tutorial

### **go** and **do**

`go` accepts a coroutine object (call of async funcion) as parameter, and start executing it concurrently (not accurate). You can expect `go` to behave the same as in golang. Except it will return an `awaitable`, which can be used with `await` or `do` when need to wait.

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

### Output:
# foo2
# foo1: 1
# foo1: 2
# hello
# world

```

### **delegate**

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

### Output:
# foo2
# foo1

```

### **Chan** and **select**

Behavior of `Chan` is similar to that in golang. `select` accepts `Chan`s as parameters, and returns when one of the `Chan`s can be read.

```python
from pygoic import Chan, select, go, do

ch1 = Chan()
ch2 = Chan()
done = Chan()

async def foo1():
    await ch1.send('world')
    print('foo1')
    ch2.close()

async def foo2():
    id, x, ok = await select(ch1, ch2)
    if id == 0:
        print(f'foo2: ch1')
    elif id == 1:
        print(f'foo2: ch2')

    id, x, ok = await select(ch1, ch2)
    if id == 0:
        print(f'foo2: ch1')
    elif id == 1:
        print(f'foo2: ch2')

    done.close()
    
go(foo1())
go(foo2())
do(done.recv())

### Output:
# foo2: ch1
# foo1
# foo2: ch2

```

### **Context**

You can expect `Context` to behave the same as in golang.

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
    
    id, x, ok = await select(ctx2.done(), ctx3.done())
    if id == 0:
        print('foo2: ctx2')
    elif id == 1:
        print('foo2: ctx3')
    
go(foo1())
go(foo2())
do(ctx3.done().recv())

### Output:
# v
# foo2: ctx2

```

### **After**, **AfterFunc** and **Timer**

Behave similar to golang.

```python
from pygoic import go, do, select, Chan
from pygoic import After, AfterFunc

ch = Chan()

async def foo1():
    ch.close()
    
async def foo2():
    AfterFunc(0.015, foo1)
    id, x, ok = await select(After(0.01), ch)
    if id == 0:
        print('foo2: after')
    elif id == 1:
        print('foo2: ch')

    id, x, ok = await select(After(0.01), ch)
    if id == 0:
        print('foo2: after')
    elif id == 1:
        print('foo2: ch')

do(foo2())

### Output:
# foo2: after
# foo2: ch

```

### **WaitGroup**

Behave similar to golang.

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

### Output:
# foo2: 0
# foo1: 0
# foo2: 1
# foo1: 1

```
