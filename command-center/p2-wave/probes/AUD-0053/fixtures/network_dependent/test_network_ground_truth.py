"""AUD-0053 ground-truth fixture A: a genuinely network-DEPENDENT test.

Deliberately makes a real outbound TCP connection and asserts on the
response. Must PASS when egress is unblocked and FAIL when the probe's
socket-level egress-block (fixtures/egress_block.py) is active -- proving
probe1's baseline-vs-blocked outcome-diff detector fires on a REAL network
dependency, not a labeled one. Also the positive control for probe2's
socket-trace: it must appear in probe2's per-test destination-host log too.
"""

from __future__ import annotations

import socket


def test_ground_truth_a_real_network_fetch_changes_outcome() -> None:
    with socket.create_connection(("example.com", 80), timeout=8) as sock:
        sock.sendall(
            b"HEAD / HTTP/1.0\r\nHost: example.com\r\nConnection: close\r\n\r\n"
        )
        data = sock.recv(128)
    assert data.startswith(b"HTTP/"), f"unexpected response head: {data!r}"
