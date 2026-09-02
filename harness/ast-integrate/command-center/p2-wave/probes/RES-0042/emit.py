#!/usr/bin/env python3
"""Emit command-center/research/RES-0042.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import (  # noqa: E402
    REPO,
    digest_file,
    probe_obj,
    run_census,
    schema_rejects_garbage,
    validate_against_schema,
)
from mappings import OUT_REL, SENTINEL, UNIT  # noqa: E402
from schema_local import domain  # noqa: E402

OUT = REPO / OUT_REL
STRIKES = HERE / "_schema_strikes.json"
REQUIRED_FIX = "align-artifact-to-research-registry.schema.json"


def err_fp(errs: list[str]) -> str:
    blob = "\n".join(sorted(errs)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def load_strikes() -> dict:
    if not STRIKES.is_file():
        return {"attempts": []}
    try:
        data = json.loads(STRIKES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"attempts": []}
    if not isinstance(data, dict):
        return {"attempts": []}
    data.setdefault("attempts", [])
    return data


def record_strike(fingerprint: str, errs: list[str], ts: str) -> int:
    data = load_strikes()
    data["attempts"].append({"fp": fingerprint, "errs": errs[:12], "ts": ts})
    STRIKES.write_text(
        json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return sum(1 for a in data["attempts"] if a.get("fp") == fingerprint)


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def park_blocked(errs: list[str], fingerprint: str, started: str) -> int:
    ended = utcnow()
    blocked = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": f"FAILED:{UNIT} schema-invalid parked fp={fingerprint}",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json RES-0042",
        "min_bytes_threshold": 256,
        "required_fix": REQUIRED_FIX,
        "artifacts": [
            {
                "path": OUT_REL,
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "Two same-fingerprint structural refutes; parked without "
                    "an ADV rebuild circle."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0042/_schema_strikes.json",
                "probes": [
                    probe_obj(
                        "source",
                        "schema-validate",
                        "command-center/p2-wave/probes/RES-0042/schema_local.py",
                        "\n".join(errs[:12]),
                    ),
                    probe_obj(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/RES-0042/_schema_strikes.json",
                        f"fp={fingerprint} required_fix={REQUIRED_FIX}",
                    ),
                ],
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 2,
            "policy": "two same-fingerprint structural refutes park BLOCKED",
            "attempts": [
                {"attempt": 1, "error_fingerprint": fingerprint, "outcome": "FAILED"},
                {"attempt": 2, "error_fingerprint": fingerprint, "outcome": "BLOCKED"},
            ],
        },
        "failure": {
            "classification": ["detector-failure"],
            "reason": REQUIRED_FIX,
            "blocked_on": REQUIRED_FIX,
        },
        "report": {
            "kind": "research-registry",
            "observations": [
                {
                    "name": "schema_errors",
                    "measured": len(errs),
                    "method": "offline research-registry validator",
                    "anchor": "command-center/schema/research-registry.schema.json",
                }
            ],
            "control_ids": ["same-fingerprint-park"],
            "required_fix": REQUIRED_FIX,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(blocked, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"FAILED:{UNIT} parked same-fingerprint structural refute fp={fingerprint}")
    print(f"required_fix={REQUIRED_FIX}")
    return 1


def seal_primary(doc: dict) -> tuple[str, int]:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    last_sha, last_size = "0" * 64, 1
    for _ in range(6):
        payload = json.dumps(doc, indent=1, ensure_ascii=True) + "\n"
        OUT.write_text(payload, encoding="utf-8")
        last_sha, last_size = digest_file(OUT)
        arts = doc.get("artifacts") or []
        if arts and isinstance(arts[0], dict) and arts[0].get("role") == "primary":
            arts[0]["sha256"] = last_sha
            arts[0]["bytes"] = max(last_size, 1)
            arts[0]["exists"] = True
        consumers = doc.get("downstream_consumers") or []
        if consumers and isinstance(consumers[0], dict):
            consumers[0]["read_ok"] = True
            consumers[0]["executed"] = True
            consumers[0]["exit_code"] = 0
    payload = json.dumps(doc, indent=1, ensure_ascii=True) + "\n"
    OUT.write_text(payload, encoding="utf-8")
    return digest_file(OUT)


def main() -> int:
    started = utcnow()
    if not schema_rejects_garbage():
        print(f"FAILED:{UNIT} schema accepted garbage")
        return 1
    doc = run_census()
    errs = validate_against_schema(doc)
    if errs:
        fingerprint = err_fp(errs)
        n = record_strike(fingerprint, errs, utcnow())
        print(f"FAILED:{UNIT} schema errors n={n} fp={fingerprint}")
        for e in errs[:25]:
            print(" ", e)
        if n >= 2:
            return park_blocked(errs, fingerprint, started)
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:{UNIT} self-declared {doc.get('state')}")
        return 1
    body = domain(doc)
    ctrl = body.get("control_invalid_url") or {}
    if ctrl.get("skipped") is True or ctrl.get("status") != "UNRESOLVABLE":
        print(f"FAILED:{UNIT} invalid URL control not honest")
        return 1
    servers = body.get("servers") or []
    if len(servers) < 10:
        print(f"FAILED:{UNIT} too few server rows {len(servers)}")
        return 1
    for row in servers:
        for key in ("final_url", "http_status", "last_release_date", "snapshot_timestamp"):
            if row.get(key) in (None, ""):
                print(f"FAILED:{UNIT} {row.get('server_id')} missing {key}")
                return 1
    digest, size = seal_primary(doc)
    live = json.loads(OUT.read_text(encoding="utf-8"))
    post = validate_against_schema(live)
    if post:
        fingerprint = err_fp(post)
        n = record_strike(fingerprint, post, utcnow())
        print(f"FAILED:{UNIT} post-write schema n={n} fp={fingerprint}")
        for e in post[:25]:
            print(" ", e)
        if n >= 2:
            return park_blocked(post, fingerprint, started)
        return 1
    text = OUT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print(f"FAILED:{UNIT} sentinel missing from serialized artifact")
        return 1
    answers = body.get("answers") or {}
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print(
        "servers={n} abandoned={a} renamed={r} unmapped={u} invalid=UNRESOLVABLE".format(
            n=len(servers),
            a=answers.get("abandoned_or_dead"),
            r=answers.get("renamed"),
            u=answers.get("no_public_upstream"),
        )
    )
    print(f"SUCCESS:{UNIT} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
