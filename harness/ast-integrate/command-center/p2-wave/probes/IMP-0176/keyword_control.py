#!/usr/bin/env python3
"""Negative control: a prose keyword matcher that MUST false-positive.

This module is not the detector. It exists so probe1 can show that scanning
description text would flag the compatible look-alike pair.
"""
from __future__ import annotations

from typing import Any, Mapping


def keyword_conflict(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    da = str(left.get("description") or "").lower()
    db = str(right.get("description") or "").lower()
    blob = da + "\n" + db
    quorum = ("unanimity" in blob) and (
        "forbid" in blob or "forbids" in blob or "forbidden" in blob
    )
    net = (
        ("egress" in blob)
        and ("air-gap" in blob or "airgap" in blob or "air-gapped" in blob)
    )
    return quorum or net
