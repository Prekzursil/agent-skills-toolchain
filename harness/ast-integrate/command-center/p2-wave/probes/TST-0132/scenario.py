"""Shared constants for TST-0132 slow-loris / read-timeout probes."""
from __future__ import annotations

# Declared read/idle timeout the production client is configured with.
READ_TIMEOUT_S = 0.35
CONNECT_TIMEOUT_S = 0.35
# Stated margin: termination must land inside read_timeout + margin.
MARGIN_S = 0.90
DEADLINE_S = READ_TIMEOUT_S + MARGIN_S

THROUGHPUT_FLOOR_BPS = 400.0
THROUGHPUT_WINDOW_S = 0.20
# 1 byte every 50ms ≈ 20 B/s, well under the floor; idle gap < read timeout
# so a connect-timeout-only client keeps reading.
TRICKLE_INTERVAL_S = 0.05
SLOW_BODY_LEN = 1_000_000
FAST_BODY = b"TST-0132-fast-payload:" + (b"A" * 2048)

# Generic unit timeout — far above the read deadline. If the client only
# has this, probe 1 fails the wall-clock bound.
UNIT_TIMEOUT_S = 5.0

GENERIC_UNIT_TIMEOUT = "unit-timeout"
NETWORK_FAULT = "network-fault"
