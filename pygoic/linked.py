
from __future__ import annotations
from typing import Generic, TypeVar


T = TypeVar('T')


class LinkedNode(Generic[T]):
    def __init__(self, list: LinkedList[T], val: T, next: LinkedNode[T], prev: LinkedNode[T]):
        self.list: LinkedList[T] = list
        self.val: T = val
        self.next: LinkedNode[T] = next
        self.prev: LinkedNode[T] = prev

    def delete(self):
        if self.list is None:
            return
        self.next.prev = self.prev
        self.prev.next = self.next
        self.list._count -= 1
        self.list = None  # type: ignore
        self.next = None  # type: ignore
        self.prev = None  # type: ignore


class LinkedList(Generic[T]):
    def __init__(self):
        self._count: int = 0
        self._head: LinkedNode[T] = LinkedNode(self, None, None, None)  # type: ignore
        self._tail: LinkedNode[T] = LinkedNode(self, None, None, None)  # type: ignore
        self._head.next = self._tail
        self._head.prev = self._tail
        self._tail.next = self._head
        self._tail.prev = self._head
        
    
    def append(self, x: T) -> LinkedNode[T]:
        n = LinkedNode(self, x, self._tail, self._tail.prev)
        n.next.prev = n
        n.prev.next = n
        self._count += 1
        return n


    def appendleft(self, x: T) -> LinkedNode[T]:
        n = LinkedNode(self, x, self._head.next, self._head)
        n.next.prev = n
        n.prev.next = n
        self._count += 1
        return n
    

    def pop(self) -> T:
        if self._count == 0:
            raise IndexError('pop from an empty LinkedList')
        n = self._tail.prev
        n.delete()
        return n.val
        
    
    def popleft(self) -> T:
        if self._count == 0:
            raise IndexError('pop from an empty LinkedList')
        n = self._head.next
        n.delete()
        return n.val
        
        
    def left(self) -> LinkedNode[T]:
        if self._count == 0:
            raise IndexError('get node from an empty LinkedList')
        return self._head.next


    def right(self) -> LinkedNode[T]:
        if self._count == 0:
            raise IndexError('get node from an empty LinkedList')
        return self._tail.prev

    
    def __len__(self):
        return self._count


    def __bool__(self):
        return self._count > 0


    def __iter__(self):
        node = self._head.next
        while node is not self._tail:
            yield node.val
            node = node.next


    def iternodes(self):
        node = self._head.next
        while node is not self._tail:
            node = node.next
            yield node.prev

