"""Find every on-disk sentence carrying one of the 8 confirmed overclaims.

Detector control (both-states): each pattern is paired with a KNOWN-PRESENT token so a zero
hit means real absence, not a broken matcher.
"""
import json
import re
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
CAS = ROOT / "command-center" / "casualty"

# (id, regex, control-regex that MUST hit somewhere in the corpus)
PATTERNS = [
    ("OC1-routed-named", r"every unmitigated cell", r"unmitigated"),
    ("OC2-all-mitigated-bypassed", r"(bypass for every|for every cell marked mitigated|All satisfied)", r"mitigated"),
    ("OC3-c5-convention", r"c1/c5|c1 and c5|family convention", r"c5"),
    ("OC4-c3-cannot", r"cannot be satisfied|fixed point", r"c3"),
    ("OC5-fresh-clone", r"fresh[- ]clone|fresh clone", r"blob"),
    ("OC6-never-dispatched", r"[Nn]ever dispatched|NEVER DISPATCHED", r"ADV-0002"),
    ("OC7a-98-transcripts", r"transcripts scanned: 98|scanned: 98", r"transcripts"),
    ("OC7b-219-of-12", r"219 files, of which 12", r"219"),
    ("OC8-sibling-committed", r"[Aa] sibling (agent )?committed", r"772159"),
]

FILES = []
for p in sorted(CAS.rglob("*")):
    if p.is_file() and p.suffix.lower() in {".md", ".json", ".py", ".sh", ".txt"}:
        if "__pycache__" in str(p):
            continue
        FILES.append(p)

print(f"corpus: {len(FILES)} files under {CAS}")
corpus = {}
for p in FILES:
    try:
        corpus[p] = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        print(f"  UNREADABLE {p}: {exc}")

failed_controls = []
for pid, pat, ctrl in PATTERNS:
    creg, reg = re.compile(ctrl), re.compile(pat)
    ctrl_hits = sum(1 for t in corpus.values() if creg.search(t))
    if ctrl_hits == 0:
        failed_controls.append(pid)
    print(f"\n=== {pid}  (control {ctrl!r} hits {ctrl_hits} files -> "
          f"{'OK' if ctrl_hits else 'DETECTOR BROKEN'})")
    for p, text in corpus.items():
        for i, line in enumerate(text.splitlines(), 1):
            if reg.search(line):
                rel = p.relative_to(ROOT).as_posix()
                print(f"  {rel}:{i}: {line.strip()[:190]}")

print("\nFAILED CONTROLS:", failed_controls or "none")
