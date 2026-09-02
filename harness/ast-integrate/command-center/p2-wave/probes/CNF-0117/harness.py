#!/usr/bin/env python3
"""Deny each CNF-0117 dependency individually and classify the outcome."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import dispatch_auth as DA
import inventory as I

LOUD = {"loud-failure", "degraded-artifact"}


def _run_consumer(env: dict[str, str], out: Path, mode: str = "loud") -> tuple[int, str, dict | None]:
    p = subprocess.run(
        [sys.executable, "-B", str(I.CONSUMER), "--out", str(out), "--mode", mode],
        cwd=str(I.REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    doc = None
    if out.is_file() and out.stat().st_size > 0:
        try:
            doc = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            doc = None
    return p.returncode, text, doc


def _base_env(catalog: Path, enrich: Path) -> dict[str, str]:
    env = os.environ.copy()
    env[I.TOKEN_ENV] = I.TOKEN_VALUE
    env[I.CATALOG_ENV] = str(catalog)
    env[I.ENRICH_ENV] = str(enrich)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def classify(dep: dict, code: int, text: str, doc: dict | None) -> dict:
    cap = dep["capability_token"]
    names = cap in text or dep["name"] in text
    if doc is not None:
        body = json.dumps(doc)
        names = names or cap in body or dep["name"] in body
        if I.TOKEN_VALUE in body:
            raise RuntimeError("consumer artifact contained the fixture token value")
    produced = doc is not None
    marked = None
    if produced and isinstance(doc, dict):
        marked = doc.get("degraded") is True
        miss = str(doc.get("missing_capability") or "")
        names = names or cap in miss or dep["name"] in miss
    if code != 0 and names:
        kind = "loud-failure"
    elif code == 0 and produced and marked is True and names:
        kind = "degraded-artifact"
    elif code == 0 and (not produced or marked is not True):
        kind = "silent-degradation"
    else:
        kind = "unclear-error"
    return {
        "dependency_id": dep["id"],
        "kind": dep["kind"],
        "deny_method": dep["deny_method"],
        "exit_code": code,
        "message": text[-800:] if text else f"exit={code}",
        "names_missing_capability": bool(names),
        "produced_artifact": produced,
        "artifact_marked_degraded": marked,
        "classification": kind,
    }


def _deny_catalog(tmp: Path) -> Path:
    # Absent path: root still cannot read a file that does not exist.
    return tmp / "absent" / "no-such-catalog.json"


def measure(*, include_mutant: bool = True) -> dict:
    I.FIXTURES.mkdir(parents=True, exist_ok=True)
    I.MINI_CATALOG.parent.mkdir(parents=True, exist_ok=True)
    if not I.MINI_CATALOG.is_file():
        I.MINI_CATALOG.write_text(
            json.dumps({"work_units": [{"id": I.UNIT, "ok": True}]}, indent=1) + "\n",
            encoding="utf-8",
        )
    credential_paths = [
        Path.home() / ".ssh" / "id_ed25519",
        Path.home() / ".cursor" / "api-key",
    ]
    before = {
        str(p): (p.stat().st_mtime_ns if p.is_file() else None) for p in credential_paths
    }
    denials: list[dict] = []
    control: dict | None = None
    mutant_row: dict | None = None

    with tempfile.TemporaryDirectory(prefix="cnf0117-") as raw:
        tmp = Path(raw)
        enrich_ok = tmp / "enrich-ok"
        enrich_ok.mkdir()
        catalog = I.MINI_CATALOG

        # Control: all dependencies present.
        cout = tmp / "control.json"
        c_env = _base_env(catalog, enrich_ok)
        c_code, c_text, c_doc = _run_consumer(c_env, cout)
        control = {
            "ran": True,
            "exit_code": c_code,
            "success": c_code == 0 and isinstance(c_doc, dict) and c_doc.get("degraded") is False,
            "artifact_degraded": bool(isinstance(c_doc, dict) and c_doc.get("degraded") is True),
            "same_run_as_denials": True,
            "message": c_text[-400:],
        }

        for dep in I.DEPS:
            out = tmp / f"deny-{dep['id']}.json"
            if dep["subject"] == "dispatch_cursor":
                code, text, _line = DA.run_gate(grant=False)
                denials.append(classify(dep, code, text, None))
                continue
            env = _base_env(catalog, enrich_ok)
            if dep["id"] == "cred-fixture-token":
                env.pop(I.TOKEN_ENV, None)
            elif dep["id"] == "perm-catalog-read":
                env[I.CATALOG_ENV] = str(_deny_catalog(tmp))
            elif dep["id"] == "perm-enrichment-write":
                enrich_bad = tmp / "enrich-is-a-file"
                enrich_bad.write_text("not-a-directory\n", encoding="utf-8")
                env[I.ENRICH_ENV] = str(enrich_bad)
            code, text, doc = _run_consumer(env, out)
            denials.append(classify(dep, code, text, doc))

        if include_mutant:
            mout = tmp / "mutant.json"
            menv = _base_env(catalog, enrich_ok)
            menv.pop(I.TOKEN_ENV, None)
            m_code, m_text, m_doc = _run_consumer(menv, mout, mode="silent")
            mutant_row = classify(I.DEPS[0], m_code, m_text, m_doc)

    after = {
        str(p): (p.stat().st_mtime_ns if p.is_file() else None) for p in credential_paths
    }
    good_classes = {row["classification"] for row in denials}
    silent_probe = {
        "mutant_classified_silent_degradation": bool(
            mutant_row and mutant_row["classification"] == "silent-degradation"
        ),
        "good_consumer_not_silent": "silent-degradation" not in good_classes,
        "fired_on_bad_state": bool(
            mutant_row and mutant_row["classification"] == "silent-degradation"
        ),
        "silent_on_good_state": "silent-degradation" not in good_classes,
        "mutant": mutant_row,
    }
    return {
        "control": control,
        "denials": denials,
        "silent_degradation_probe": silent_probe,
        "all_denials_loud_or_degraded": all(
            row["classification"] in LOUD for row in denials
        ),
        "credential_safety": {
            "no_real_credential_modified": before == after,
            "credential_denials_used_unset_variable": all(
                row["deny_method"] == "unset-variable-in-subprocess"
                for row in denials
                if row["kind"] == "credential"
            ),
            "no_credential_value_in_artifact": True,
            "fixture_token_never_copied": I.TOKEN_VALUE
            not in json.dumps({"denials": denials, "control": control}),
        },
    }
