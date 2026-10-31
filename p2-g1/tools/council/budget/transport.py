"""Transport token count independent of governor whitespace words."""
from __future__ import annotations

import math


def transport_token_count(text: str) -> int:
    n = len(str(text or "").encode("utf-8"))
    return int(math.ceil(n / 4))
