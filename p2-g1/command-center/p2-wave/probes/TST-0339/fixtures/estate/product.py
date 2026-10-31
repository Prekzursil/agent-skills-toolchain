"""Estate fixture: reconstructed DEFAULT_MIN_BYTES hole (TST-0339).

The DEFAULT_MIN_BYTES default at :16 is UNEXERCISED: every test supplies
min_bytes explicitly, so mutating the module constant cannot turn the
suite red - the measured hole this unit replays.
"""

DEFAULT_MIN_BYTES = 1024


def _norm(data):
    return data if isinstance(data, bytes) else bytes(data)



def check_payload_floor(data, min_bytes=DEFAULT_MIN_BYTES):
    """Reject payloads below the floor; tests always supply min_bytes."""
    data = _norm(data)
    if len(data) < min_bytes:
        return "REJECT"
    return "OK"




def scale_by_factor(x, factor=2):
    """EXERCISED default: test_scale_omitted omits factor on purpose."""
    return x * factor
