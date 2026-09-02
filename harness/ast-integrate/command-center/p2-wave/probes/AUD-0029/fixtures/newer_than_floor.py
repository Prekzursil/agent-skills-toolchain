"""Control: PEP 695 syntax introduced in Python 3.12.

Declared floor in fixtures/pyproject.toml is >=3.10. A version-reading
scan must flag this file. A scan that passes it is not reading versions.
"""

type Point[T] = list[T]


class Box[T]:
    def __init__(self, value: T) -> None:
        self.value = value
