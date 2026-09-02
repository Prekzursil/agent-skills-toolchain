#!/usr/bin/env python3
import json
from pathlib import Path

pins = json.loads((Path(__file__).resolve().parent / "pins.json").read_text(encoding="utf-8"))
want = "1.0.0"
have = str(pins.get("widget", ""))
if have != want:
    print(f"FAIL:pin-mismatch widget want={want} have={have}")
    raise SystemExit(1)
print("PASS:pkg-widget")
