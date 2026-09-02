"""Canary-seeded dual-scanner scenario for TST-0206.

Plant the canary in a process env dict and in local config, prove both
scanners fire on a planted-inside-artifact control, then scan produced
artifact directories. A leaky producer and a credential-in-bundle zip are
the dirty states so a zero on the clean trees is not a dead scanner.

The full canary never appears in the public result dict.
"""
from __future__ import annotations

import json
import secrets
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import canary as C
import entropy_scan as E
import pattern_scan as P

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

LIVE_PRODUCED = (
    "command-center/receipts",
    "command-center/confirmation",
)
OPTIONAL_PRODUCED = (
    "command-center/events",
    "dist",
    "release",
    "build",
)
# Enumerator liveness: a known-present produced receipt. Prefer IMP-0317.json
# (original named file); if that receipt is absent, fall back to another
# non-empty JSON under receipts/.
_LIVENESS_PREFERRED = (
    "command-center/receipts/IMP-0317.json",
    "command-center/receipts/TST-0208.json",
    "command-center/receipts/TST-0204.json",
)


def _liveness() -> tuple[str, Path, bool]:
    for rel in _LIVENESS_PREFERRED:
        path = REPO / rel
        try:
            if path.is_file() and path.stat().st_size > 0:
                return rel, path, True
        except OSError:
            continue
    receipts = REPO / "command-center/receipts"
    if receipts.is_dir():
        for path in sorted(receipts.glob("*.json")):
            try:
                if path.is_file() and path.stat().st_size > 0:
                    rel = path.relative_to(REPO).as_posix()
                    return rel, path, True
            except OSError:
                continue
    rel = _LIVENESS_PREFERRED[0]
    return rel, REPO / rel, False

PEM_HEADER = b"-----BEGIN RSA PRIVATE KEY-----\n"
PEM_FOOTER = b"\n-----END RSA PRIVATE KEY-----\n"


@dataclass
class ScenarioResult:
    public: dict[str, Any]
    _full: str

    def contains_canary(self, blob: bytes | str) -> bool:
        return C.blob_contains(blob, self._full)


def _census(root: Path) -> dict[str, int]:
    files = 0
    nbytes = 0
    if root.is_file():
        try:
            return {"files": 1, "bytes": int(root.stat().st_size)}
        except OSError:
            return {"files": 0, "bytes": 0}
    if not root.is_dir():
        return {"files": 0, "bytes": 0}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        files += 1
        try:
            nbytes += p.stat().st_size
        except OSError:
            pass
    return {"files": files, "bytes": nbytes}


def _surface(
    *,
    sid: str,
    method: str,
    pattern_hits: list,
    entropy_hits: list,
    canary_pattern: list,
    canary_entropy: list,
    census: dict[str, int],
    known_present_found: bool,
    extra: dict | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": sid,
        "method": method,
        "files_scanned": census["files"],
        "bytes_scanned": census["bytes"],
        "pattern_hit_count": len(pattern_hits),
        "entropy_hit_count": len(entropy_hits),
        "pattern_canary_hits": len(canary_pattern),
        "entropy_canary_hits": len(canary_entropy),
        "known_present_found": known_present_found,
        "pattern_fired": len(pattern_hits) > 0,
        "entropy_fired": len(entropy_hits) > 0,
        "pattern_public": [P.public_hit(h) for h in pattern_hits[:12]],
        "entropy_public": [E.public_hit(h) for h in entropy_hits[:12]],
    }
    if extra:
        row.update(extra)
    return row


def _scan_pair(root: Path, *, origin: str, full: str):
    pattern_hits = P.scan_tree(root, origin=origin)
    entropy_hits = E.scan_tree(root, origin=origin)
    return (
        pattern_hits,
        entropy_hits,
        P.canary_hits(pattern_hits),
        E.matching_canary(entropy_hits, full, prefix_len=len(C.PREFIX)),
        _census(root),
    )


def run_scenario() -> ScenarioResult:
    token = C.mint()
    full = token.full
    regression_secret = secrets.token_urlsafe(32)
    pem_body = secrets.token_urlsafe(48).encode("ascii")

    with tempfile.TemporaryDirectory(prefix="tst0206-") as td:
        root = Path(td)

        env = {C.ENV_KEYS[0]: full, C.ENV_KEYS[1]: full}
        config = root / "local_config"
        config.mkdir()
        (config / ".env").write_text(
            f"{C.ENV_KEYS[0]}={full}\n{C.ENV_KEYS[1]}={full}\n",
            encoding="utf-8",
        )
        (config / "secrets.json").write_text(
            json.dumps(
                {
                    "api_token": full,
                    "note": "local config, not a produced artifact",
                }
            ),
            encoding="utf-8",
        )
        env_planted = env[C.ENV_KEYS[0]] == full and env[C.ENV_KEYS[1]] == full
        config_planted = full in (config / ".env").read_text(
            encoding="utf-8"
        ) and full in (config / "secrets.json").read_text(encoding="utf-8")

        cfg_p, cfg_e, cfg_cp, cfg_ce, cfg_c = _scan_pair(
            config, origin="local_config", full=full
        )

        control = root / "control_artifact"
        control.mkdir()
        (control / "bundle.json").write_text(
            json.dumps(
                {
                    "role": "detector-control",
                    "embedded": full,
                    "note": "planted INSIDE an artifact before any zero is trusted",
                }
            ),
            encoding="utf-8",
        )
        ctl_p, ctl_e, ctl_cp, ctl_ce, ctl_c = _scan_pair(
            control, origin="control_artifact", full=full
        )

        clean = root / "produced_clean"
        clean.mkdir()
        (clean / "receipt.json").write_text(
            json.dumps(
                {
                    "unit": "sandbox-producer",
                    "state": "SUCCESS",
                    "note": "producer did not copy env or local config into the artifact",
                    "sha256": "0" * 64,
                }
            ),
            encoding="utf-8",
        )
        cln_p, cln_e, cln_cp, cln_ce, cln_c = _scan_pair(
            clean, origin="produced_clean", full=full
        )

        leaky = root / "produced_leaky"
        leaky.mkdir()
        (leaky / "receipt.json").write_text(
            json.dumps(
                {
                    "unit": "leaky-producer",
                    "environ": {k: env[k] for k in C.ENV_KEYS},
                    "note": "both-states dirty: planted env keys dumped into a produced receipt",
                }
            ),
            encoding="utf-8",
        )
        lky_p, lky_e, lky_cp, lky_ce, lky_c = _scan_pair(
            leaky, origin="produced_leaky", full=full
        )

        bundle_dir = root / "regression_src"
        bundle_dir.mkdir()
        (bundle_dir / "decrypted.json").write_text(
            json.dumps(
                {
                    "password": regression_secret,
                    "decrypted_secret": regression_secret,
                    "note": "regression seed: credentials entered an artifact bundle",
                }
            ),
            encoding="utf-8",
        )
        (bundle_dir / "synthetic.pem").write_bytes(PEM_HEADER + pem_body + PEM_FOOTER)
        bundle_zip = root / "regression_bundle" / "payload.zip"
        bundle_zip.parent.mkdir()
        with zipfile.ZipFile(bundle_zip, "w") as zf:
            zf.write(bundle_dir / "decrypted.json", "decrypted.json")
            zf.write(bundle_dir / "synthetic.pem", "synthetic.pem")
            zf.writestr("README.md", "sandbox bundle for TST-0206 regression seed\n")
        reg_p, reg_e, _reg_cp, _reg_ce, reg_c = _scan_pair(
            bundle_zip.parent, origin="regression_bundle", full=full
        )
        cred_rules = {"json-password", "json-secret-field", "pem-private-key"}
        reg_pattern_fired = any(h.rule_id in cred_rules for h in reg_p)
        reg_entropy_fired = len(reg_e) > 0

        live_rows: list[dict[str, Any]] = []
        live_pattern_canary = 0
        live_entropy_canary = 0
        live_files = 0
        live_bytes = 0
        required_absent: list[str] = []
        liveness_rel, liveness_path, liveness = _liveness()
        for rel in LIVE_PRODUCED:
            path = REPO / rel
            if not path.is_dir():
                required_absent.append(rel)
                live_rows.append(
                    {
                        "id": f"live:{rel}",
                        "method": "filesystem walk of produced artifact directory",
                        "known_present_found": False,
                        "absent": True,
                        "pattern_canary_hits": 0,
                        "entropy_canary_hits": 0,
                    }
                )
                continue
            lp, le, lcp, lce, lc = _scan_pair(path, origin=rel, full=full)
            live_pattern_canary += len(lcp)
            live_entropy_canary += len(lce)
            live_files += lc["files"]
            live_bytes += lc["bytes"]
            known = liveness if rel.endswith("/receipts") else lc["files"] > 0
            live_rows.append(
                _surface(
                    sid=f"live:{rel}",
                    method="filesystem walk of produced artifact directory (bytes, one zip nesting)",
                    pattern_hits=lp,
                    entropy_hits=le,
                    canary_pattern=lcp,
                    canary_entropy=lce,
                    census=lc,
                    known_present_found=known,
                    extra={"absent": False},
                )
            )
        optional_absent = [rel for rel in OPTIONAL_PRODUCED if not (REPO / rel).exists()]

        detector_agree = len(ctl_cp) > 0 and len(ctl_ce) > 0
        clean_zero = len(cln_cp) == 0 and len(cln_ce) == 0
        leaky_agree = len(lky_cp) > 0 and len(lky_ce) > 0
        live_zero = live_pattern_canary == 0 and live_entropy_canary == 0
        config_visible = len(cfg_cp) > 0 and len(cfg_ce) > 0
        regression_agree = reg_pattern_fired and reg_entropy_fired
        scanners_agree = (
            detector_agree
            and leaky_agree
            and regression_agree
            and clean_zero
            and live_zero
            and config_visible
        )
        ok = (
            env_planted
            and config_planted
            and config_visible
            and detector_agree
            and clean_zero
            and leaky_agree
            and regression_agree
            and live_zero
            and liveness
            and live_files > 0
            and not required_absent
            and scanners_agree
        )
        public = {
            "unit_id": "TST-0206",
            "canary_prefix": C.PREFIX,
            "canary_sha256": token.sha256,
            "canary_len": token.full_len,
            "planting": {
                "env_keys": list(C.ENV_KEYS),
                "config_files": [".env", "secrets.json"],
                "env_contains_canary": env_planted,
                "config_contains_canary": config_planted,
                "scanners_see_config": config_visible,
                "pattern_canary_hits": len(cfg_cp),
                "entropy_canary_hits": len(cfg_ce),
            },
            "detector_control": _surface(
                sid="detector-control-artifact",
                method="pattern scanner + independent entropy scanner over planted artifact",
                pattern_hits=ctl_p,
                entropy_hits=ctl_e,
                canary_pattern=ctl_cp,
                canary_entropy=ctl_ce,
                census=ctl_c,
                known_present_found=detector_agree,
                extra={"agree": detector_agree},
            ),
            "produced_clean": _surface(
                sid="produced-clean-sandbox",
                method="pattern scanner + independent entropy scanner over sandbox produced dir",
                pattern_hits=cln_p,
                entropy_hits=cln_e,
                canary_pattern=cln_cp,
                canary_entropy=cln_ce,
                census=cln_c,
                known_present_found=cln_c["files"] > 0,
                extra={"agree_zero": clean_zero},
            ),
            "produced_leaky": _surface(
                sid="produced-leaky-env-dump",
                method="same two scanners over a producer that dumped planted env keys",
                pattern_hits=lky_p,
                entropy_hits=lky_e,
                canary_pattern=lky_cp,
                canary_entropy=lky_ce,
                census=lky_c,
                known_present_found=leaky_agree,
                extra={"agree_present": leaky_agree},
            ),
            "regression_bundle": _surface(
                sid="regression-credential-bundle",
                method="zipfile member scan (not include-rules) by both scanners",
                pattern_hits=reg_p,
                entropy_hits=reg_e,
                canary_pattern=[],
                canary_entropy=[],
                census=reg_c,
                known_present_found=regression_agree,
                extra={
                    "pattern_credential_fired": reg_pattern_fired,
                    "entropy_fired": reg_entropy_fired,
                    "agree_dirty": regression_agree,
                    "pattern_rule_ids": sorted({h.rule_id for h in reg_p}),
                },
            ),
            "live_produced": {
                "dirs": list(LIVE_PRODUCED),
                "optional_absent_not_scanned_as_clean": optional_absent,
                "required_absent": required_absent,
                "files_scanned": live_files,
                "bytes_scanned": live_bytes,
                "pattern_canary_hits": live_pattern_canary,
                "entropy_canary_hits": live_entropy_canary,
                "enumerator_liveness": liveness,
                "liveness_path": liveness_rel,
                "agree_zero": live_zero,
                "surfaces": live_rows,
            },
            "agreement": {
                "detector_control": detector_agree,
                "produced_clean_zero": clean_zero,
                "produced_leaky_present": leaky_agree,
                "regression_dirty": regression_agree,
                "live_produced_zero": live_zero,
                "config_visible": config_visible,
                "both_scanners_agree": scanners_agree,
            },
            "inputs_absent": {
                "tools/lib/security.mjs": not (REPO / "tools/lib/security.mjs").is_file(),
                "command-center/schema/receipt.schema.json": not (
                    REPO / "command-center/schema/receipt.schema.json"
                ).is_file(),
            },
            "pass": ok,
        }
        return ScenarioResult(public=public, _full=full)
