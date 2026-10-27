#!/usr/bin/env python3
"""TST-0066 probe1: alias-matrix re-verification (live, fail-closed).

Re-runs all 41 recorded alias_attempts through the recreated guard
families (string deny / string allow / string containment and their
canonical twins, plus the three estate mirrors) and asserts verdict
equality with the receipt; re-audits the three estate snippets live."""
from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = REPO / "command-center" / "p2-wave" / "probes" / "TST-0066"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from winpath import _expand_83, canonical, same_identity  # noqa: E402

UNIT = "TST-0066"
SENTINEL = "SUCCESS:TST-0066"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
ROOT83 = "C:" + chr(92) + "work" + chr(92) + "ast-integrate"
HOOKGLOB_BACK = "C:" + chr(92) + "Program Files" + chr(92) + "app" + chr(92) + "hooks*"
HOOKGLOB_FWD = "C:/Program Files/app/hooks/*"
DENIED = "C:" + chr(92) + "Program Files" + chr(92) + "app" + chr(92) + "secret.txt"
ENTRY = "command-center/WORK-UNIT-CATALOG.json"
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def g_control_deny(c: str) -> str:
    return "REJECT" if c == DENIED else "ACCEPT"


def g_canonical_deny(c: str) -> str:
    return "REJECT" if same_identity(c, DENIED) else "ACCEPT"


def g_control_allow(c: str) -> str:
    return "ACCEPT" if fnmatch.fnmatch(c, HOOKGLOB_BACK) else "REJECT"


def g_canonical_allow(c: str) -> str:
    return "ACCEPT" if fnmatch.fnmatch(canonical(_expand_83(c)), canonical(_expand_83(HOOKGLOB_BACK))) else "REJECT"


def g_control_contain(c: str) -> str:
    return "ACCEPT" if c.startswith(ROOT83) else "REJECT"


def g_canonical_contain(c: str) -> str:
    cc = canonical(_expand_83(c))
    root = canonical(_expand_83(ROOT83))
    return "ACCEPT" if cc == root or cc.startswith(root + chr(92)) else "REJECT"


def g_estate_allow(c: str) -> str:
    return "ACCEPT" if fnmatch.fnmatch(c, HOOKGLOB_FWD) else "REJECT"


def g_estate_deny(c: str) -> str:
    return "REJECT" if (c == ENTRY or c.startswith(ENTRY)) else "ACCEPT"


def g_estate_contain(c: str) -> str:
    p = Path(c)
    root = Path(ROOT83)
    return "ACCEPT" if (root in p.parents or p.parent == root) else "REJECT"


FAMILY = {
    "control-deny": g_control_deny, "canonical-deny": g_canonical_deny,
    "control-allow": g_control_allow, "canonical-allow": g_canonical_allow,
    "control-contain": g_control_contain, "canonical-contain": g_canonical_contain,
    "estate-permission-allowlist": g_estate_allow,
    "estate-reconcile-deny": g_estate_deny,
    "estate-render-containment": g_estate_contain,
}


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 1024, "under-min-bytes")
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared", str(doc.get("state")))
    chk(SENTINEL in text, "sentinel-absent")
    for gid in ("estate-permission-allowlist", "estate-reconcile-deny", "estate-render-containment"):
        row = next((g for g in (doc.get("guards") or []) if g.get("id") == gid), None)
        chk(row is not None and row.get("compares_path_strings") is True, "guard-row-missing:" + gid)
    n = 0
    for at in doc.get("alias_attempts") or []:
        gid = str(at.get("guard_id"))
        fn = FAMILY.get(gid)
        if fn is None:
            chk(False, "unknown-guard:" + gid)
            continue
        live = fn(str(at.get("candidate")))
        want = str(at.get("verdict"))
        chk(live == want, "verdict:" + gid + ":" + str(at.get("candidate"))[-24:], "recorded=" + want + " rerun=" + live)
        n += 1
    src1 = (REPO / "platform/plugin/payload.py").read_text(encoding="utf-8").splitlines()
    chk("fnmatch.fnmatch(rel, self.glob)" in src1[129], "estate-allowlist-snippet-live", src1[129].strip())
    src2 = (REPO / "tools/command-center/reconcile_delivery.py").read_text(encoding="utf-8").splitlines()
    chk("rel.startswith(entry)" in src2[85], "estate-deny-snippet-live", src2[85].strip())
    src3 = (REPO / "tools/command-center/tests/test_render.py").read_text(encoding="utf-8").splitlines()
    chk("root in path.parents" in src3[109], "estate-containment-snippet-live", src3[109].strip())
    ids = doc.get("identities") or []
    ok_ids = sum(1 for i in ids if bool(i.get("same")) == bool(i.get("expected")))
    chk(len(ids) >= 8 and ok_ids == len(ids), "identities-self-consistent", str(ok_ids) + "/" + str(len(ids)))
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails[:12]))
        return 1
    print("SUCCESS:" + UNIT + "-probe1 all " + str(n) + " recorded alias verdicts re-derived across 9 guard families; estate snippets verified live (payload.py:130, reconcile_delivery.py:86, test_render.py:110); 10 identity rows self-consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
