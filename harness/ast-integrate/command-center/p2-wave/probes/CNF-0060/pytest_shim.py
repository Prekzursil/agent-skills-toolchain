"""Minimal pytest.mark / pytest.skip shim so fixtures run without pytest installed."""
from __future__ import annotations


class Skip(BaseException):
    def __init__(self, reason: str = "") -> None:
        self.reason = reason
        super().__init__(reason)


def _append_mark(fn, mark: dict) -> None:
    marks = list(getattr(fn, "_cnf60_marks", []))
    marks.append(mark)
    fn._cnf60_marks = marks


class _Mark:
    def skip(self, reason: str = ""):
        def deco(fn):
            _append_mark(fn, {"type": "skip", "reason": reason})
            return fn

        return deco

    def skipif(self, condition, *, reason: str = ""):
        def deco(fn):
            _append_mark(
                fn,
                {
                    "type": "skipif",
                    "reason": reason,
                    "condition": bool(condition),
                },
            )
            return fn

        return deco

    def xfail(self, reason: str = ""):
        def deco(fn):
            _append_mark(fn, {"type": "xfail", "reason": reason})
            return fn

        return deco


class _Pytest:
    mark = _Mark()

    @staticmethod
    def skip(reason: str = "") -> None:
        raise Skip(reason)


pytest = _Pytest()
