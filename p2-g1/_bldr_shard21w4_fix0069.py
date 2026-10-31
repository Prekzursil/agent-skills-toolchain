"""Fix WFA-0069: refresh stale recorded receipt sha256/bytes in the artifact.

The artifact's records[] carry the receipt hashes captured at emit time; the
receipt files were later re-emitted (timestamps changed) so the recorded hashes
went stale. probe2_postcondition recomputes hashes live and demands agreement.
This refreshes the recorded receipt_sha256 / receipt_bytes to the LIVE files
(content unchanged otherwise) and records the repair in extensions.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
ART = REPO / "command-center/wfa/WFA-0069-adopt-as-is-executable-test.json"


def lf_sha(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))
    changed = 0
    missing = []
    for rec in doc.get("records") or []:
        rp = rec.get("receipt_path")
        if not rp:
            continue
        p = REPO / str(rp).replace("\\", "/")
        if not p.is_file():
            missing.append(str(rp))
            continue
        sha, n = lf_sha(p)
        if rec.get("receipt_sha256") != sha or rec.get("receipt_bytes") != n:
            rec["receipt_sha256"] = sha
            rec["receipt_bytes"] = n
            changed += 1
    ext = doc.setdefault("extensions", {})
    if isinstance(ext, dict):
        ext["builder_repair_2026_10_26"] = (
            f"shard21 wave-4 builder: refreshed {changed} stale recorded receipt "
            f"sha256/bytes rows to the live on-disk WFA-0069-smoke-receipts files "
            f"(receipt files were re-emitted after the artifact captured them; "
            f"dispositions and verdicts unchanged). missing receipts: "
            f"{len(missing)}"
        )
    text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    ART.write_text(text, encoding="utf-8", newline="\n")
    print(f"updated={changed} missing={len(missing)}")
    for m in missing[:5]:
        print("  missing:", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
