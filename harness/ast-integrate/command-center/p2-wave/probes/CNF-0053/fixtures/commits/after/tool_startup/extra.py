"""Import-time payload added in commit-after (largest expected increase).

Reads a sibling payload file so cold filesystem cache is a real cost, and
blocks for a deterministic interval so the before/after wall delta is larger
than interpreter-spawn noise even on a heavily loaded host (measured IQR on
the measurement box exceeds 1.4s, so the planted regression must be well
above that floor to be detectable).
"""

import time
from pathlib import Path

PAYLOAD_NAME = "_payload.bin"
_PAYLOAD_PATH = Path(__file__).with_name(PAYLOAD_NAME)
if not _PAYLOAD_PATH.is_file():
    raise FileNotFoundError(f"missing import-time payload: {_PAYLOAD_PATH}")
_PAYLOAD = _PAYLOAD_PATH.read_bytes()
PAYLOAD_BYTES = len(_PAYLOAD)
_DELAY_S = 3.0
_t0 = time.perf_counter()
time.sleep(_DELAY_S)
while time.perf_counter() - _t0 < _DELAY_S:
    pass
