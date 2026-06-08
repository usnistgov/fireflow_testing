from typing import TypeVar, Callable

X = TypeVar("X")
Y = TypeVar("Y")


def maybe(default: Y, f: Callable[[X], Y], x: X | None) -> Y:
    return default if x is None else f(x)


def fmap_maybe(f: Callable[[X], Y], x: X | None) -> Y | None:
    return maybe(None, f, x)


def key_maybe(xs: dict[X, Y], key: X) -> Y | None:
    try:
        return xs[key]
    except KeyError:
        return None


def esc(s: str) -> str:
    return s.replace("\n", "\\n").replace("\0", "\\0")
