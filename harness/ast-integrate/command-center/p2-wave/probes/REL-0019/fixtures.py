"""Labelled known-good / known-bad fixtures for the five shipped gates."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
COMP = FIX / "completion"

CAPABILITY_INDEX: list[dict[str, Any]] = [
    {
        "capability_id": "cap.lint-python",
        "name": "lint-python",
        "kind": "skill",
        "description": "lint python source files with ruff or pylint",
        "triggers": {
            "keywords": ["lint", "ruff", "pylint"],
            "verbs": ["lint"],
            "globs": ["*.py"],
        },
        "negative_scope": ["weather", "recipe", "sports"],
    },
    {
        "capability_id": "cap.extract-pdf",
        "name": "extract-pdf",
        "kind": "skill",
        "description": "extract text from pdf documents",
        "triggers": {
            "keywords": ["pdf", "extract"],
            "verbs": ["extract"],
            "globs": ["*.pdf"],
        },
        "negative_scope": ["weather"],
    },
    {
        "capability_id": "cap.scan-credentials",
        "name": "scan-credentials",
        "kind": "skill",
        "description": "scan a tree for credential store paths",
        "triggers": {
            "keywords": ["credential", "secret", "scanner"],
            "verbs": ["scan"],
        },
        "negative_scope": ["example only"],
    },
]


def _md_body(i: int) -> str:
    pad = "abcdefghijklmnopqrstuvwxyz0123456789 " * 8
    return (
        f"Fixture body {i:02d} for the completion predicate. "
        "This paragraph exists so the artifact is not a sentinel-only stub. "
        "Measured rates need a labelled known-good document with distinct characters "
        "and enough non-space text to clear the thin-body floor. "
        f"Unique token sequence: alpha-{i:02d}-bravo-charlie-delta-echo. "
        + pad
        + "\n"
    )


def materialize_completion() -> None:
    COMP.mkdir(parents=True, exist_ok=True)
    for i in range(20):
        sid = f"SUCCESS:FX-COMP-GOOD-{i:02d}"
        if i < 10:
            doc = {
                "state": "SUCCESS",
                "sentinel": sid,
                "body": _md_body(i),
                "fixture": True,
            }
            (COMP / f"good_{i:02d}.json").write_text(
                json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        else:
            (COMP / f"good_{i:02d}.md").write_text(
                sid + "\n\n" + _md_body(i), encoding="utf-8"
            )
    for i in range(20):
        path = COMP / f"bad_{i:02d}.json"
        if i < 5:
            path.write_bytes(b"")
        elif i < 10:
            path.write_text(
                json.dumps({"state": "BLOCKED", "sentinel": "no"}, indent=2) + "\n",
                encoding="utf-8",
            )
        elif i < 14:
            path.write_text("{not-json", encoding="utf-8")
        elif i < 17:
            sid = f"SUCCESS:FX-COMP-BAD-{i:02d}"
            md = COMP / f"bad_{i:02d}.md"
            md.write_text(sid + "\n", encoding="utf-8")
        else:
            # missing file: do not write bad_17/18/19.json
            if path.exists():
                path.unlink()


def completion_fixtures() -> list[dict[str, Any]]:
    materialize_completion()
    out: list[dict[str, Any]] = []
    for i in range(20):
        rel = (
            f"command-center/p2-wave/probes/REL-0019/fixtures/completion/good_{i:02d}.json"
            if i < 10
            else f"command-center/p2-wave/probes/REL-0019/fixtures/completion/good_{i:02d}.md"
        )
        sid = f"SUCCESS:FX-COMP-GOOD-{i:02d}"
        out.append(
            {
                "id": f"comp-good-{i:02d}",
                "label": "good",
                "expect_fire": False,
                "payload": {
                    "id": f"FX-COMP-GOOD-{i:02d}",
                    "output_path": rel,
                    "completion_sentinel": sid,
                },
            }
        )
    for i in range(20):
        if i < 14:
            rel = f"command-center/p2-wave/probes/REL-0019/fixtures/completion/bad_{i:02d}.json"
            sid = ""
        elif i < 17:
            rel = f"command-center/p2-wave/probes/REL-0019/fixtures/completion/bad_{i:02d}.md"
            sid = f"SUCCESS:FX-COMP-BAD-{i:02d}"
        else:
            rel = f"command-center/p2-wave/probes/REL-0019/fixtures/completion/missing_{i:02d}.json"
            sid = "SUCCESS:MISSING"
        out.append(
            {
                "id": f"comp-bad-{i:02d}",
                "label": "bad",
                "expect_fire": True,
                "payload": {
                    "id": f"FX-COMP-BAD-{i:02d}",
                    "output_path": rel,
                    "completion_sentinel": sid,
                },
            }
        )
    return out


def _materialize_credential_content() -> None:
    cred = FIX / "credential"
    cred.mkdir(parents=True, exist_ok=True)
    for i in range(10):
        body = (
            f"# ordinary config {i:02d}\n"
            "command = status\n"
            f"note = ordinary-record-{i:02d}\n"
            "path = tools/harness-drift/harness_drift.py\n"
        )
        (cred / f"good_{i:02d}.py").write_text(body, encoding="utf-8")
    # Documented example shapes from platform/plugin/test_package.py / SECRET_RULES.
    # Values are synthetic; scan_secrets records a shape, never the value.
    bads = [
        'TOKEN = "ghp_' + ("b" * 40) + '"\n',
        'TOKEN = "sk-' + ("c" * 30) + '"\n',
        'KEY = "AKIAIOSFODNN7EXAMPLE"\n',
        'TOKEN = "sk-ant-' + ("d" * 24) + '"\n',
        'TOKEN = "xoxb-' + ("e" * 12) + '"\n',
        'TOKEN = "hf_' + ("f" * 30) + '"\n',
        'TOKEN = "eyJhbGciOiJIUzI1NiIs.eyJzdWIiOiIxMjM0NTY.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV"\n',
        "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAK8=\n",
        'password = "sixteencharsxxxx"\n',
        'KEY = "ASIAIOSFODNN7EXAMPLE"\n',
    ]
    for i, body in enumerate(bads):
        (cred / f"bad_{i:02d}.py").write_text(body, encoding="utf-8")


def credential_fixtures() -> list[dict[str, Any]]:
    """Labelled inputs for platform/plugin/payload.py (the shipped scanner)."""
    _materialize_credential_content()
    good_paths = [
        "src/app.py",
        "README.md",
        "docs/guide.md",
        "package.json",
        "tests/test_example.py",
        "command-center/ready_units.py",
        "command-center/p2-wave/probes/REL-0019/gates.py",
        "hooks/skill-router/route.py",
        "tools/harness-drift/harness_drift.py",
        "platform/plugin/payload.py",
    ]
    bad_paths = [
        ".env",
        ".env.local",
        "secrets.pem",
        "id_rsa",
        "credentials.json",
        "auth.json",
        ".netrc",
        "foo.credentials",
        "service-token.json",
        "id_ed25519",
    ]
    out: list[dict[str, Any]] = []
    for i, p in enumerate(good_paths):
        out.append(
            {
                "id": f"cred-good-path-{i:02d}",
                "label": "good",
                "expect_fire": False,
                "payload": {"kind": "path", "path": p},
            }
        )
    for i in range(10):
        rel = f"command-center/p2-wave/probes/REL-0019/fixtures/credential/good_{i:02d}.py"
        out.append(
            {
                "id": f"cred-good-content-{i:02d}",
                "label": "good",
                "expect_fire": False,
                "payload": {
                    "kind": "content",
                    "file": str(FIX / "credential" / f"good_{i:02d}.py"),
                    "rel": rel,
                },
            }
        )
    for i, p in enumerate(bad_paths):
        out.append(
            {
                "id": f"cred-bad-path-{i:02d}",
                "label": "bad",
                "expect_fire": True,
                "payload": {"kind": "path", "path": p},
            }
        )
    for i in range(10):
        rel = f"command-center/p2-wave/probes/REL-0019/fixtures/credential/bad_{i:02d}.py"
        out.append(
            {
                "id": f"cred-bad-content-{i:02d}",
                "label": "bad",
                "expect_fire": True,
                "payload": {
                    "kind": "content",
                    "file": str(FIX / "credential" / f"bad_{i:02d}.py"),
                    "rel": rel,
                },
            }
        )
    return out


def capability_fixtures() -> list[dict[str, Any]]:
    FIX.mkdir(parents=True, exist_ok=True)
    (FIX / "capability_index.json").write_text(
        json.dumps(CAPABILITY_INDEX, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    out: list[dict[str, Any]] = []
    lint_q = [f"lint python module {i:02d} with ruff" for i in range(10)]
    pdf_q = [f"extract text from report-{i:02d}.pdf" for i in range(5)]
    scan_q = [f"scan credential store paths in tree {i:02d}" for i in range(5)]
    for i, q in enumerate(lint_q + pdf_q + scan_q):
        out.append(
            {
                "id": f"cap-bad-{i:02d}",
                "label": "bad",
                "expect_fire": True,
                "payload": {"query": q, "index": CAPABILITY_INDEX},
            }
        )
    nofit = (
        [f"what is the weather in city-{i:02d}" for i in range(10)]
        + [f"bake a chocolate recipe {i:02d}" for i in range(5)]
        + [f"sports score for team {i:02d}" for i in range(5)]
    )
    for i, q in enumerate(nofit):
        out.append(
            {
                "id": f"cap-good-{i:02d}",
                "label": "good",
                "expect_fire": False,
                "payload": {"query": q, "index": CAPABILITY_INDEX},
            }
        )
    return out


def near_dup_fixtures() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(20):
        left = f"completion predicate rejects empty artifacts case {i:02d}"
        right = f"the completion predicate rejects empty artifacts case {i:02d}"
        out.append(
            {
                "id": f"dup-bad-{i:02d}",
                "label": "bad",
                "expect_fire": True,
                "payload": {"left": left, "right": right, "threshold": 0.5},
            }
        )
    distinct = [
        (
            f"lint python source files item {i:02d}",
            f"extract text from pdf documents item {i:02d}",
        )
        for i in range(20)
    ]
    for i, (left, right) in enumerate(distinct):
        out.append(
            {
                "id": f"dup-good-{i:02d}",
                "label": "good",
                "expect_fire": False,
                "payload": {"left": left, "right": right, "threshold": 0.5},
            }
        )
    return out


def drift_fixtures() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(10):
        body = f"same-bytes-line-{i:02d}\nsecond-line\n"
        out.append(
            {
                "id": f"drift-good-ident-{i:02d}",
                "label": "good",
                "expect_fire": False,
                "payload": {"repo": body, "live": body},
            }
        )
    for i in range(10):
        repo = f"eol-line-{i:02d}\r\nsecond\r\n"
        live = f"eol-line-{i:02d}\nsecond\n"
        out.append(
            {
                "id": f"drift-good-eol-{i:02d}",
                "label": "good",
                "expect_fire": False,
                "payload": {"repo": repo, "live": live},
            }
        )
    for i in range(20):
        repo = f"repo-unique-{i:02d}\nshared-line\n"
        live = f"live-unique-{i:02d}\nshared-line\n"
        out.append(
            {
                "id": f"drift-bad-{i:02d}",
                "label": "bad",
                "expect_fire": True,
                "payload": {"repo": repo, "live": live},
            }
        )
    return out


FIXTURE_BUILDERS = {
    "completion_predicate": completion_fixtures,
    "credential_scanner": credential_fixtures,
    "capability_router": capability_fixtures,
    "near_duplicate_detector": near_dup_fixtures,
    "drift_detector": drift_fixtures,
}

GATE_ORDER = list(FIXTURE_BUILDERS)


def load_all() -> dict[str, list[dict[str, Any]]]:
    return {gid: builder() for gid, builder in FIXTURE_BUILDERS.items()}
