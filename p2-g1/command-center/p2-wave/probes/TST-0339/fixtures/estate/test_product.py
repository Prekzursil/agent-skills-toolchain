"""Fixture suite: 3 calls SUPPLY min_bytes (0 omit it); scale gets 1 supply + 1 omit."""
from product import DEFAULT_MIN_BYTES, check_payload_floor, scale_by_factor


def test_floor_rejects_below_supplied():
    assert check_payload_floor(b"x" * 10, min_bytes=100) == "REJECT"


def test_floor_ok_supplied():
    assert check_payload_floor(b"x" * 200, min_bytes=100) == "OK"


def test_floor_boundary_supplied():
    assert check_payload_floor(b"x" * 1024, min_bytes=DEFAULT_MIN_BYTES) == "OK"


def test_scale_omitted():
    assert scale_by_factor(21) == 42


def test_scale_supplied():
    assert scale_by_factor(21, factor=3) == 63


def main():
    failed = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError as exc:
                failed.append((name, str(exc)))
    for name, why in failed:
        print(f"FAILED {name}: {why}")
    print(f"ran=5 failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
