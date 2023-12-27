
from __future__ import annotations
from typing import Generic, TypeVar


T = TypeVar('T')


class LinkedNode(Generic[T]):
    def __init__(self, val: T, next: LinkedNode[T], prev: LinkedNode[T]):
        self.val: T = val
        self.next: LinkedNode[T] = next
        self.prev: LinkedNode[T] = prev

    def _remove(self) -> bool:
        if self.next is None or self.prev is None:
            return False
        self.next.prev = self.prev
        self.prev.next = self.next
        self.next = None  # type: ignore
        self.prev = None  # type: ignore
        return True


class LinkedList(Generic[T]):
    def __init__(self):
        self._count: int = 0
        self._head: LinkedNode[T] = LinkedNode(None, None, None)  # type: ignore
        self._tail: LinkedNode[T] = LinkedNode(None, None, None)  # type: ignore
        self._head.next = self._tail
        self._head.prev = self._tail
        self._tail.next = self._head
        self._tail.prev = self._head
        
    
    def append(self, x: T) -> LinkedNode[T]:
        n = LinkedNode(x, self._tail, self._tail.prev)
        n.next.prev = n
        n.prev.next = n
        self._count += 1
        return n
    
    def appendleft(self, x: T) -> LinkedNode[T]:
        n = LinkedNode(x, self._head.next, self._head)
        n.next.prev = n
        n.prev.next = n
        self._count += 1
        return n
    

    def pop(self) -> T:
        if self._count == 0:
            raise IndexError('pop from an empty LinkedList')
        n = self._tail.prev
        n.prev.next = self._tail
        n.next.prev = n.prev
        n.next = None  # type: ignore
        n.prev = None  # type: ignore
        self._count -= 1
        return n.val
        
    
    def popleft(self) -> T:
        if self._count == 0:
            raise IndexError('pop from an empty LinkedList')
        n = self._head.next
        n.next.prev = self._head
        n.prev.next = n.next
        n.next = None  # type: ignore
        n.prev = None  # type: ignore
        self._count -= 1
        return n.val
        
        
    def left(self) -> LinkedNode[T]:
        if self._count == 0:
            raise IndexError('get node from an empty LinkedList')
        return self._head.next


    def right(self) -> LinkedNode[T]:
        if self._count == 0:
            raise IndexError('get node from an empty LinkedList')
        return self._tail.prev


    def remove(self, node: LinkedNode[T]):
        if node._remove():
            self._count -= 1

    
    def __len__(self):
        return self._count


    def __bool__(self):
        return self._count > 0


    def __iter__(self):
        node = self._head.next
        while node is not self._tail:
            yield node.val


    def iternodes(self):
        node = self._head.next
        while node is not self._tail:
            node = node.next
            yield node.prev

