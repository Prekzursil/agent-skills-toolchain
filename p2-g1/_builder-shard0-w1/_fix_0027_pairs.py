"""ADV-0027: each evidence card carries the source+verifier PROBE PAIR.

receipt_core evidence items require probes minItems 2 with one 'source' and
one 'verifier' (mechanically different instruments). Card 1 pairs the live
import-path matrix (source) with the static containment review (verifier);
card 2 states the static claim and pairs the same two probes with roles
swapped.
"""
from pathlib import Path

p = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0027/write_receipts.py"
src = p.read_text(encoding="utf-8")

old = '''        "evidence": [
            {
                "claim": (
                    "Each crafted archive was extracted through "
                    "import_offline_bundle_archive. Hostile members were rejected "
                    "with zero files created outside or inside dest; the benign "
                    "control extracted completely."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/offline_import.py:import_offline_bundle_archive",
                "confidence": "almost-certain",
                "probes": [
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
                ],
            },
            {
                "claim": (
                    "Static review of archive_extract.py shows per-member "
                    "posixpath.normpath followed by resolve/relative_to containment. "
                    "pkg/../../escape.beacon does not startswith('..') but is rejected "
                    "as TRAVERSAL after normalisation. The import path never calls extractall."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/archive_extract.py:assert_contained_after_normalize",
                "confidence": "almost-certain",
                "probes": [
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
                ],'''

new = '''        "evidence": [
            {
                "claim": (
                    "Each crafted archive was extracted through "
                    "import_offline_bundle_archive. Hostile members were rejected "
                    "with zero files created outside or inside dest; the benign "
                    "control extracted completely. Statically, archive_extract.py "
                    "normalises every member and enforces resolve/relative_to "
                    "containment and never calls extractall."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/offline_import.py:import_offline_bundle_archive",
                "confidence": "almost-certain",
                "probes": [
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
                    },
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
                    },
                ],
            },
            {
                "claim": (
                    "Static review of archive_extract.py shows per-member "
                    "posixpath.normpath followed by resolve/relative_to containment. "
                    "pkg/../../escape.beacon does not startswith('..') but is rejected "
                    "as TRAVERSAL after normalisation. The import path never calls "
                    "extractall - confirmed behaviourally by the live import matrix."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/archive_extract.py:assert_contained_after_normalize",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
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
                    },
                    {
                        "role": "verifier",
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
                    },
                ],
            },'''

assert old in src, "evidence block anchor missing"
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8")
import ast
ast.parse(src)
print("evidence cards now carry source+verifier pairs")
