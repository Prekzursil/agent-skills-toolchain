"""Planted control: comments claim no download; body fetches get-pip.py.

Estate precedent named by AUD-0053: 14 tests silently downloaded get-pip.py
while comments asserted they never download. This fixture is that class.
PASS requires the HTTP GET to succeed. On an air-gapped host it fails in
both states (TOUCH, not DEPEND). The companion test_connect_attempt_permitted
is the DEPEND control that still flips when the OS has no route.
"""
from __future__ import annotations

import urllib.request

# this test never downloads get-pip.py
GET_PIP = "https://bootstrap.pypa.io/get-pip.py"


def test_silent_get_pip_download() -> None:
    req = urllib.request.Request(GET_PIP, method="GET")
    with urllib.request.urlopen(req, timeout=3) as resp:
        chunk = resp.read(32)
    if not chunk:
        raise AssertionError("get-pip.py response was empty")
