#!/usr/bin/env python3
"""Load-bearing quality gate for claim.ship-ready. Planted FAIL."""
SHIP_READY = False
if not SHIP_READY:
    raise SystemExit("CNL-0068 bound test failed: claim.ship-ready is not ready")
raise SystemExit(0)
