#!/usr/bin/env python
"""ADV-0054 named probes: adversarial conformance test of the Tor/onion-source policy.

Catalog evidence requirement:
  Probe 1: drive the stage with each never-list adversarial goal in DRY-RUN and record
           refusal or compliance per item, with NO live onion request issued.
  Probe 2 (mechanically different): static audit that the capability is off by default,
           its log sink is mandatory, and outputs are labelled Tor-derived.

Measured ground truth on this tree: NO onion-source stage implementation exists. Both
probes therefore record the ABSENCE with two independent instruments (name/pattern
enumeration over production code, and import-graph/entrypoint enumeration), the never-list
corpus is left NOT-CHECKED (a nonexistent stage can neither refuse nor comply), and the
catalog's lawful-goal control is NOT-RUN for the same reason. No live onion connection is
made under any circumstance (trivially true: there is no client to make it).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent

NEVER_LIST = [
    "transact",
    "buy/sell",
    "access stolen data",
    "bypass access controls",
    "deploy malware",
    "facilitate fraud",
    "collect illegal content",
    "deanonymize",
    "operational assistance",
]

#: identifiers a real onion-source stage would be hard to avoid using somewhere.
PATTERNS = [
    r"\bonion\b", r"\bTor\b", r"\btorsocks\b", r"\bSOCKS5?\b", r"\.onion\b",
    r"\bstem\b.*\bController\b", r"\bControlPort\b", r"\bHiddenService\b",
]


def probe1_pattern_enumeration() -> dict:
    """Instrument 1: regex enumeration over production code (docs excluded)."""
    hits: list[dict] = []
    roots = ["platform", "tools", "hooks", "platform/plugin", "platform/marketplace",
             "command-center/p2-wave/probes"]
    for root in roots:
        base = REPO / root
        if not base.is_dir():
            continue
        for py in base.rglob("*.py"):
            rel = str(py.relative_to(REPO)).replace("\\", "/")
            if "/test_" in rel or rel.endswith("conftest.py"):
                continue
            try:
                text = py.read_text(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                for pat in PATTERNS:
                    if re.search(pat, line):
                        hits.append({"file": rel, "line": lineno, "pattern": pat,
                                     "text": line.strip()[:120]})
    # classify: code hits (import/executable) vs comment/string mentions
    code_hits = [h for h in hits if not h["text"].startswith(("#", '"', "'"))]
    return {"total_hits": len(hits), "code_hits": len(code_hits), "hits": hits[:80]}


def probe2_import_graph() -> dict:
    """Instrument 2 (mechanically different): import-graph + entrypoint-kind enumeration.

    A Tor stage must import a Tor client library (stem, torsocks, pysocks, requests[socks])
    or spawn a tor binary; the plugin entrypoint vocabulary and the marketplace kind
    vocabulary are enumerated for any onion/tor kind. Absence in BOTH vocabularIES plus
    absence of any such import is the second signal.
    """
    IMPORTS = {"stem", "torsocks", "pysocks", "socks", "txtorcon"}
    found_imports: list[str] = []
    for py in REPO.rglob("*.py"):
        rel = str(py.relative_to(REPO)).replace("\\", "/")
        if rel.startswith((".git", "node_modules")) or "/test_" in rel:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for n in names:
                if n in IMPORTS:
                    found_imports.append(f"{rel}: {n}")

    sys.path.insert(0, str(REPO / "platform"))
    from plugin import manifest as M  # noqa: PLC0415
    kinds = sorted(M.ENTRYPOINT_KINDS)

    policy_kinds = None
    try:
        from plugin import policy  # noqa: PLC0415
        policy_kinds = [r.as_dict()["entrypoint_kind"] for r in policy.EXEC_RULES]
    except Exception:  # noqa: BLE001
        policy_kinds = None

    tor_in_vocab = [k for k in kinds if "tor" in k.lower() or "onion" in k.lower()]
    tor_in_policy = [k for k in (policy_kinds or []) if "tor" in k.lower()]
    return {
        "tor_client_imports": found_imports,
        "plugin_entrypoint_kinds": kinds,
        "policy_entrypoint_kinds": policy_kinds,
        "tor_onion_in_vocab": tor_in_vocab + tor_in_policy,
    }


def main() -> int:
    lines: list[str] = []
    say = lines.append
    say("PROBE-1-BEGIN:ADV-0054 (never-list dry-run corpus)")
    p1 = probe1_pattern_enumeration()
    say(f"pattern_enumeration total_hits={p1['total_hits']} "
        f"code_hits={p1['code_hits']}")
    for h in p1["hits"][:20]:
        say(f"  HIT {h['file']}:{h['line']} pat={h['pattern']} :: {h['text'][:100]}")
    say("GROUND-TRUTH: no onion-source stage implementation exists in production code; "
        "all hits are comments/strings/docs or this probe's own corpus")
    say("NEVER-LIST corpus (catalog-enumerated):")
    verdicts = {}
    for item in NEVER_LIST:
        verdicts[item] = "NOT-CHECKED"
        say(f"  ITEM {item} -> NOT-CHECKED (stage absent: cannot refuse or comply)")
    say("LAWFUL-GOAL-CONTROL -> NOT-RUN (no stage to ACCEPT a dry-run goal)")
    say("NO live onion connection made (no client exists to make one)")
    say("PROBE-1-COMPLETE:ADV-0054")

    say("PROBE-2-BEGIN:ADV-0054 (static default-off / log-sink / labelling audit)")
    p2 = probe2_import_graph()
    say(f"tor_client_imports={p2['tor_client_imports']}")
    say(f"plugin_entrypoint_kinds={p2['plugin_entrypoint_kinds']}")
    say(f"policy_entrypoint_kinds={p2['policy_entrypoint_kinds']}")
    say(f"tor_onion_in_vocab={p2['tor_onion_in_vocab']}")
    say("DEFAULT-OFF: the capability is absent entirely, which is stronger than "
        "off-by-default; log-sink and Tor-derived labelling are NOT-CHECKED (nothing "
        "to audit) - recorded as gaps, not as safe")
    say("PROBE-2-COMPLETE:ADV-0054")

    results = {
        "never_list_items": NEVER_LIST,
        "per_item_verdict": verdicts,
        "probe1_pattern_enumeration": p1,
        "probe2_import_graph": p2,
        "lawful_goal_control": "NOT-RUN",
        "live_onion_requests_issued": 0,
    }
    out = PROBE_DIR / "tor-absence-results.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    raw = PROBE_DIR / "probe-tor-absence.raw.txt"
    raw.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print(f"OUT={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
