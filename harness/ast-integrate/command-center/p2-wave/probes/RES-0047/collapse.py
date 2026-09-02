"""Shared-primitive collapse for RES-0047.

Sources that share one upstream primitive count as ONE signal
(05-ECO section 6: npm/PyPI/Homebrew signing share one OIDC primitive).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def collapse_groups(signals: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ungrouped: list[str] = []
    for row in signals:
        pid = row.get("shared_primitive_id")
        sid = str(row.get("id") or "")
        if isinstance(pid, str) and pid.strip():
            by_id[pid.strip()].append(row)
        else:
            ungrouped.append(sid)

    groups = []
    collapsed = 0
    for pid, members in sorted(by_id.items()):
        extra = max(0, len(members) - 1)
        if extra:
            collapsed += extra
        groups.append(
            {
                "shared_primitive_id": pid,
                "member_ids": [str(m.get("id")) for m in members],
                "member_registries": [str(m.get("registry")) for m in members],
                "raw_count": len(members),
                "independent_count": 1,
                "collapsed_extras": extra,
            }
        )

    raw = len(signals)
    return {
        "raw_signal_rows": raw,
        "ungrouped_signal_ids": ungrouped,
        "groups": groups,
        "collapsed_shared_primitive_signals": collapsed,
        "independent_signals_after_collapse": raw - collapsed,
        "rule": (
            "Independence is asserted, not assumed: rows that share "
            "shared_primitive_id count as one signal. collapsed_shared_primitive_signals "
            "is sum(len(group)-1) over groups with a shared primitive id."
        ),
    }
