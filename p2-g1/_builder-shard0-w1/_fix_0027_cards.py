"""ADV-0027 write_receipts: probe cards to the current receipt_core shape.

- fingerprint is REQUIRED on probe cards (stable digest of (method, command),
  max 12 chars, source != verifier)
- 'id' is not a legal property on a probe card (additionalProperties: false)
- exit_code must be an integer or omitted (never null)
"""
import hashlib
from pathlib import Path

p = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0027/write_receipts.py"
src = p.read_text(encoding="utf-8")

old1 = """                "probes": [
                    {
                        "id": "probe1",
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": p1_raw,
                        "exit_code": probes[0]["exit_code"] if probes else None,
                    }
                ],"""
new1 = """                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": p1_raw,
                        "fingerprint": hashlib.sha256(
                            ("command|" + P1).encode("utf-8")
                        ).hexdigest()[:12],
                        **(
                            {"exit_code": probes[0]["exit_code"]}
                            if probes
                            else {}
                        ),
                    }
                ],"""
assert old1 in src, "probe1 card anchor missing"
src = src.replace(old1, new1, 1)

old2 = """                "probes": [
                    {
                        "id": "probe2",
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": p2_raw,
                        "exit_code": probes[1]["exit_code"] if probes and len(probes) > 1 else None,
                    }
                ],"""
new2 = """                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": p2_raw,
                        "fingerprint": hashlib.sha256(
                            ("command|" + P2).encode("utf-8")
                        ).hexdigest()[:12],
                        **(
                            {"exit_code": probes[1]["exit_code"]}
                            if probes and len(probes) > 1
                            else {}
                        ),
                    }
                ],"""
assert old2 in src, "probe2 card anchor missing"
src = src.replace(old2, new2, 1)

if "import hashlib" not in src:
    src = src.replace("import json\n", "import hashlib\nimport json\n", 1)
p.write_text(src, encoding="utf-8")
import ast
ast.parse(src)
print("write_receipts cards fixed")
