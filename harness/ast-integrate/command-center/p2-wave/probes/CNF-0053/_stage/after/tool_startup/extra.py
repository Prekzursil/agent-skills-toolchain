"""Import-time payload added in commit-after (largest expected increase).

Reads a sibling payload file so cold filesystem cache is a real cost, and
spins a short deterministic loop so the before/after wall delta is larger
than interpreter noise on a warm page cache.
"""

import time
from pathlib import Path

PAYLOAD_NAME = "_payload.bin"
_PAYLOAD_PATH = Path(__file__).with_name(PAYLOAD_NAME)
if not _PAYLOAD_PATH.is_file():
    raise FileNotFoundError(f"missing import-time payload: {_PAYLOAD_PATH}")
_PAYLOAD = _PAYLOAD_PATH.read_bytes()
PAYLOAD_BYTES = len(_PAYLOAD)
_t0 = time.perf_counter()
while time.perf_counter() - _t0 < 0.012:
    pass
