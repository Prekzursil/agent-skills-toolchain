"""AUD-0053 ground-truth fixture B: a test that TOUCHES the network but
swallows the failure, so its outcome never changes -- deliberately modeling
the catalog's own measured precedent ("14 tests silently downloading
get-pip.py despite comments saying otherwise"). This is invisible to
probe1's outcome-diff (it PASSES either way, blocked or not) and must be
caught ONLY by probe2's socket-level trace naming the destination host --
exactly the gap the catalog's evidence_requirement calls out: "the blocked
run finds tests that DEPEND on the network and the trace finds tests that
merely TOUCH it."

This test's own docstring/comment claims hermeticity; the assertion below
does not depend on the fetch outcome, so a reviewer skimming green CI would
never suspect it reaches the network at all.
"""

from __future__ import annotations

import socket


def test_ground_truth_b_silent_network_touch_claims_hermetic() -> None:
    # Hermetic per this comment -- no assertion depends on network state.
    try:
        with socket.create_connection(("example.com", 80), timeout=5) as sock:
            sock.sendall(
                b"HEAD / HTTP/1.0\r\nHost: example.com\r\nConnection: close\r\n\r\n"
            )
            sock.recv(1)
    except OSError:
        pass  # silently swallowed -- this is the exact defect shape being audited
    assert 1 + 1 == 2
