#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
HERE = REPO / "command-center" / "p2-wave" / "probes" / "CNF-0098"
sys.path.insert(0, str(HERE))
import estate as E  # noqa: E402

ART = REPO / "command-center" / "confirmation" / "CNF-0098-macos-reachability.json"
MAN = HERE / "UNIT-ARTIFACT-MANIFEST.json"
REL = "command-center/confirmation/CNF-0098-macos-reachability.json"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> None:
    live = E.signal_command()
    doc = json.loads(ART.read_text(encoding="utf-8"))
    proofs = list(doc.get("two_signal_proof") or [])
    found = False
    for p in proofs:
        if isinstance(p, dict) and p.get("method") == "command":
            p["fingerprint"] = live["fingerprint"]
            p["observation"] = live["observation"]
            p["this_host_darwin"] = live["this_host_darwin"]
            found = True
    if not found:
        proofs.append(
            {
                "method": "command",
                "fingerprint": live["fingerprint"],
                "observation": live["observation"],
                "this_host_darwin": live["this_host_darwin"],
            }
        )
    doc["two_signal_proof"] = proofs
    doc["this_host_darwin"] = bool(live["this_host_darwin"])
    if live["this_host_darwin"] and not doc.get("macos_reachable"):
        doc["macos_reachable"] = True
    ART.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    sha, size = digest(ART)
    man = json.loads(MAN.read_text(encoding="utf-8"))
    for a in man.get("artifacts") or []:
        if a.get("unit_id") == "CNF-0098" and str(a.get("path") or "").replace("\\", "/") == REL:
            a["sha256"] = sha
            a["bytes"] = size
            a["present"] = True
    MAN.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("patched CNF-0098 fp", live["fingerprint"][:16], "darwin", live["this_host_darwin"])


if __name__ == "__main__":
    main()
