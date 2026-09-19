# CNF-0015 reviewer step 2: resolve the 3 sha256 mismatches - CRLF phantom or real drift?
import hashlib
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\agent-skills-toolchain")
rec = json.loads(
    (
        REPO / "command-center" / "confirmation" / "CNF-0015-blocker-repro.json"
    ).read_text(encoding="utf-8")
)

print("=== STEP 2a: EOL-normalized custody re-check ===")
for art in rec["artifacts"]:
    p = REPO / art["path"]
    b = p.read_bytes()
    raw_ok = hashlib.sha256(b).hexdigest() == art["sha256"]
    crlf = b.count(b"\r\n")
    norm_ok = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest() == art["sha256"]
    verdict = (
        "raw-match"
        if raw_ok
        else ("crlf-phantom (normalized-match)" if norm_ok else "REAL DRIFT")
    )
    print(
        f"{verdict}: {art['path']} bytes={len(b)} crlf_pairs={crlf} lines~{b.count(b'\n')}"
    )

print("\n=== STEP 2b: pytest.out content (on-disk) ===")
print(
    (
        REPO / "command-center" / "p2-wave" / "probes" / "CNF-0015" / "pytest.out"
    ).read_text(encoding="utf-8", errors="replace")
)

print("=== STEP 2c: UNIT-ARTIFACT-MANIFEST.json (on-disk) ===")
man = (
    REPO
    / "command-center"
    / "p2-wave"
    / "probes"
    / "CNF-0015"
    / "UNIT-ARTIFACT-MANIFEST.json"
)
print(man.read_text(encoding="utf-8", errors="replace")[:1500])

print("\n=== STEP 2d: fixture 07 pre vs post byte-identity ===")
pre07 = (
    REPO
    / "command-center/p2-wave/probes/CNF-0015/fixtures/pre-fix/07-OPTION-UNIVERSE.md"
).read_bytes()
post07 = (
    REPO
    / "command-center/p2-wave/probes/CNF-0015/fixtures/post-fix/07-OPTION-UNIVERSE.md"
).read_bytes()
print(f"pre07 == post07: {pre07 == post07} ({len(pre07)}B vs {len(post07)}B)")

print("\n=== STEP 2e: OPTION-ID-RESOLUTION.json key facts (corroboration of 31) ===")
oir = json.loads(
    (REPO / "command-center" / "OPTION-ID-RESOLUTION.json").read_text(encoding="utf-8")
)
print("top-level keys:", list(oir.keys())[:20])


def hunt(obj, depth=0, hits=None):
    if hits is None:
        hits = []
    if depth > 4:
        return hits
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if any(
                t in kl for t in ("shared", "collision", "intersect", "count")
            ) and isinstance(v, (int, str, bool)):
                hits.append((k, v))
            hunt(v, depth + 1, hits)
    elif isinstance(obj, list):
        for v in obj[:80]:
            hunt(v, depth + 1, hits)
    return hits


for k, v in hunt(oir)[:25]:
    print(f"  {k} = {v}")
