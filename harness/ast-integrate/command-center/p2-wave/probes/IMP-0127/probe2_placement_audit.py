#!/usr/bin/env python3
"""Named probe 2: structural audit of the single placement call site + plant."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from marketplace.audit import audit_directories, audit_live  # noqa: E402
from plugin.errors import MissingTransactionIdError  # noqa: E402
from plugin.install import install_from_handoff  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0127.json"
PLANTED_PLUGIN = """

@file_placement_call_site
def _planted_second_placement_site(dest, blob: bytes) -> None:
    (dest / "planted").write_bytes(blob)
"""
PLANTED_MARKETPLACE = """

def _planted_marketplace_placement(dest, blob: bytes) -> None:
    dest.write_bytes(blob)
"""


def _copy_pkg(src: Path, dst: Path) -> None:
    for path in src.rglob("*.py"):
        rel = path.relative_to(src)
        if "tests" in rel.parts or "__pycache__" in rel.parts:
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0127-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:IMP-0127" not in text or doc.get("unit_id") != "IMP-0127":
        print("FAILED:IMP-0127-probe2 receipt identity")
        return 1

    live = audit_live(REPO)
    if not live["ok"] or live["placement_site_count"] != 1:
        print("FAILED:IMP-0127-probe2 live audit")
        print(json.dumps(live, indent=2)[:4000])
        return 1
    site = live["sites"][0]
    if site["package"] != "plugin" or site["name"] != "place_payload_files":
        print("FAILED:IMP-0127-probe2 site not plugin.place_payload_files", site)
        return 1
    if live["marketplace_writes"] or live["writes_outside_site"]:
        print("FAILED:IMP-0127-probe2 extra writes")
        print(json.dumps({"mkt": live["marketplace_writes"], "out": live["writes_outside_site"]}))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0127-p2-") as tmp:
        tree = Path(tmp)
        plugin_copy = tree / "plugin"
        mkt_copy = tree / "marketplace"
        _copy_pkg(TOOLS / "plugin", plugin_copy)
        _copy_pkg(TOOLS / "marketplace", mkt_copy)
        clean = audit_directories(plugin_copy, mkt_copy)
        if not clean["ok"]:
            print("FAILED:IMP-0127-probe2 copy of live tree failed audit")
            return 1

        placement = plugin_copy / "placement.py"
        placement.write_text(
            placement.read_text(encoding="utf-8") + PLANTED_PLUGIN, encoding="utf-8"
        )
        planted = audit_directories(plugin_copy, mkt_copy)
        if planted["ok"] or planted["placement_site_count"] != 2:
            print("FAILED:IMP-0127-probe2 planted plugin site not caught")
            print(json.dumps({k: planted[k] for k in ("ok", "placement_site_count", "reasons")}))
            return 1

        placement.write_text(
            placement.read_text(encoding="utf-8").replace(PLANTED_PLUGIN, ""),
            encoding="utf-8",
        )
        install_py = mkt_copy / "install.py"
        install_py.write_text(
            install_py.read_text(encoding="utf-8") + PLANTED_MARKETPLACE,
            encoding="utf-8",
        )
        planted_mkt = audit_directories(plugin_copy, mkt_copy)
        if planted_mkt["ok"] or not planted_mkt["marketplace_writes"]:
            print("FAILED:IMP-0127-probe2 planted marketplace write not caught")
            print(json.dumps({k: planted_mkt[k] for k in ("ok", "reasons", "marketplace_writes")}))
            return 1

    with tempfile.TemporaryDirectory(prefix="imp0127-bypass-") as tmp2:
        dest = Path(tmp2) / "dest"
        bypass = False
        try:
            install_from_handoff("not-a-handoff", dest)
        except MissingTransactionIdError as exc:
            msg = str(exc).lower()
            bypass = "transaction_id" in msg or "untyped" in msg
        except Exception as exc:  # noqa: BLE001 — any other exception is a miss
            print(f"FAILED:IMP-0127-probe2 bypass raised {type(exc).__name__}: {exc}")
            return 1
        if dest.exists():
            print("FAILED:IMP-0127-probe2 untyped call placed files")
            return 1
        if not bypass:
            print("FAILED:IMP-0127-probe2 untyped call was not a visible bypass")
            return 1

    summary = {
        "probe": "probe2-placement-audit",
        "unit_id": "IMP-0127",
        "pass": True,
        "live_site_count": live["placement_site_count"],
        "live_site": site,
        "planted_plugin_caught": True,
        "planted_marketplace_caught": True,
        "direct_untyped_bypass_visible": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "SUCCESS:IMP-0127-probe2 exactly one placement call site; "
        "planted second site fails; direct bypass without transaction id is visible"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
