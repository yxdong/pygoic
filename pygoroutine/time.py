


from typing import Any, Callable


class Timer:
    
    def stop(self) -> bool:
        return True



def AfterFunc(d: float, f: Callable[[], Any]) -> Timer:
    pass