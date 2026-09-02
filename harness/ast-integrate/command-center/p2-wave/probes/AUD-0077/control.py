"""Plant a synthetic token in a scratch tree; require BOTH scanners to find it.

The token body never leaves this module except as a local variable that is
checked for leakage and then discarded.
"""
from __future__ import annotations

import json
import secrets
import tempfile
from pathlib import Path

from entropy_scan import scan_tree
from gitleaks_scan import run_gitleaks
from helpers import assert_absent

VARIABLE = "AUD77_SYNTHETIC_API_KEY"
BASENAME = "aud77-canary.env"
ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _token() -> tuple[str, str]:
    # GitHub PAT *shape* so gitleaks github-pat fires; high Shannon so entropy fires.
    body = "".join(secrets.choice(ALPHABET) for _ in range(36))
    return "ghp_" + body, body


def run_control() -> dict:
    token, body = _token()
    with tempfile.TemporaryDirectory(prefix="aud77-ctrl-") as tmp:
        root = Path(tmp)
        planted = root / BASENAME
        planted.write_text(
            f"# synthetic AUD-0077 canary — not a live credential\n{VARIABLE}={token}\n",
            encoding="utf-8",
        )
        gl = run_gitleaks(root)
        ent = scan_tree(root)
        gl_hit = any(
            h.get("variable_name") == VARIABLE or h["path"].endswith(BASENAME) for h in gl
        )
        ent_hit = any(
            h.get("variable_name") == VARIABLE or h["path"].endswith(BASENAME) for h in ent["findings"]
        )
        gl_blob = json.dumps(gl, sort_keys=True)
        ent_blob = json.dumps(ent, sort_keys=True)
        assert_absent(gl_blob, body, "gitleaks-control-report")
        assert_absent(ent_blob, body, "entropy-control-report")
        assert_absent(gl_blob, token, "gitleaks-control-token")
        assert_absent(ent_blob, token, "entropy-control-token")
        result = {
            "variable_name": VARIABLE,
            "planted_basename": BASENAME,
            "gitleaks_found": gl_hit,
            "entropy_found": ent_hit,
            "both_found": bool(gl_hit and ent_hit),
            "gitleaks_found": gl_hit,
            "entropy_found": ent_hit,
            "both_found": bool(gl_hit and ent_hit),
            "gitleaks_rule_ids": sorted({h["rule_id"] for h in gl}),
            "entropy_rule_ids": sorted({h["rule_id"] for h in ent["findings"]}),
            "token_body_absent_from_scanner_reports": True,
            "scratch_not_in_repo": True,
        }
    # token/body go out of scope with the function; never returned.
    return result

run_control = run_control
