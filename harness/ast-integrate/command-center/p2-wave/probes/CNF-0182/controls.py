"""Known-broken control: a mutated package input must fail."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from common import PACKAGES, digest_file
from executil import run_cmd


def mutant_goes_red(claim_id: str = "CLAIM-P0-001") -> dict:
    src = PACKAGES / claim_id
    if not src.is_dir():
        raise FileNotFoundError(src)
    tmp = Path(tempfile.mkdtemp(prefix="cnf0182-mutant-"))
    try:
        dest = tmp / claim_id
        shutil.copytree(src, dest)
        payload = dest / "inputs" / "payload.json"
        doc = json.loads(payload.read_text(encoding="utf-8"))
        if "id" in doc:
            doc["id"] = "CNF-9999"
        elif "$schema" in doc:
            doc["$schema"] = "http://json-schema.org/draft-99/schema#"
        else:
            doc["__mutated__"] = True
        payload.write_text(
            json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        sha, _ = digest_file(payload)
        pkg = json.loads((dest / "PACKAGE.json").read_text(encoding="utf-8"))
        pkg["inputs"][0]["sha256"] = sha
        (dest / "PACKAGE.json").write_text(
            json.dumps(pkg, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        mutant_cmd = (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/CNF-0182/run_one.py "
            f"--package {dest}"
        )
        orig_cmd = pkg["one_command"]
        mutant_rc, mutant_tail = run_cmd(mutant_cmd)
        orig_rc, orig_tail = run_cmd(orig_cmd)
        return {
            "claim_id": claim_id,
            "mutant_exit": mutant_rc,
            "original_exit": orig_rc,
            "went_red": mutant_rc != 0,
            "original_still_green": orig_rc == 0,
            "mutant_tail": mutant_tail[-500:],
            "orig_tail": orig_tail[-500:],
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
