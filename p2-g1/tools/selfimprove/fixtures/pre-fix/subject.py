#!/usr/bin/env python3
"""Pre-fix subject: empty identifiers are accepted (RED)."""


def accepts_id(value: str) -> bool:
    return True


if __name__ == "__main__":
    ok = accepts_id("")
    if ok:
        print("CASE empty-id-accepted")
        print("SUMMARY failed=1")
        raise SystemExit(1)
    print("SUMMARY failed=0")
