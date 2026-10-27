#!/usr/bin/env python3
"""Post-fix subject: empty identifiers are rejected (GREEN)."""


def accepts_id(value: str) -> bool:
    return bool(value)


if __name__ == "__main__":
    if accepts_id(""):
        print("CASE empty-id-accepted")
        print("SUMMARY failed=1")
        raise SystemExit(1)
    print("SUMMARY failed=0")
