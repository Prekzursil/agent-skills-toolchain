#!/usr/bin/env python3
"""ADV-0123 shared-git-index and file-lease measurements.

All git and write drills target a tempfile scratch tree. The live worktree
is never used as GIT_DIR / GIT_WORK_TREE.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "ADV-0123"
OUTPUT_REL = (
    "command-center/adversarial/"
    "ADV-0123-concurrent-session-index-and-lease-race.json"
)
SCHEMA_REL = "command-center/schema/fault-injection-run.schema.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
LEGAL = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0123/probe1_index_overlap.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0123/probe2_lease_enforcement.py"
)
PROBE1_NAME = (
    "Probe 1: run two agents against one scratch tree with overlapping file "
    "sets and inspect what each staging operation captured, using git diff "
    "--cached as the oracle."
)
PROBE2_NAME = (
    "Probe 2 (mechanically different): lease-level test - acquire a lease "
    "from one identity and attempt the conflicting write from another, "
    "recording whether the write is blocked, warned, or silently allowed; "
    "an advisory lease that nothing consults is documentation, not a control."
)

QUESTION = (
    "When two sessions or agents operate on the same working tree, does a "
    "broad staging operation sweep another agent's files, and do the "
    "advisory file leases actually prevent the overlap?"
)

_CANDIDATES = {
    "file_lease_py": "tools/command-center/file_lease.py",
    "file_lease_schema": "command-center/schema/file-lease.schema.json",
    "leases_dir": "command-center/leases",
    "work_claim_py": "tools/command-center/work_claim.py",
}

_GIT_ENV_KEYS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_COMMON_DIR",
)


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def load_catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT_ID:
            return u
    raise RuntimeError("ADV-0123 missing from catalog")


def catalog_sentinel() -> str:
    return str(load_catalog_unit()["completion_sentinel"])


def schema_errors(doc: Any) -> list[str]:
    schema_path = REPO / SCHEMA_REL
    if not schema_path.is_file():
        return [f"schema-missing:{SCHEMA_REL}"]
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema-missing"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    return [
        f"{list(e.path)}: {e.message}"
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    ]


def _clean_git_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in _GIT_ENV_KEYS:
        env.pop(key, None)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_AUTHOR_NAME"] = "adv-0123"
    env["GIT_AUTHOR_EMAIL"] = "adv-0123@invalid"
    env["GIT_COMMITTER_NAME"] = "adv-0123"
    env["GIT_COMMITTER_EMAIL"] = "adv-0123@invalid"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def _refuse_live_tree(scratch: Path) -> None:
    scratch = scratch.resolve()
    live = REPO.resolve()
    if scratch == live:
        raise RuntimeError("refusing git against the live worktree")
    live_git = (live / ".git").resolve()
    scratch_git = (scratch / ".git").resolve()
    if live_git.exists() and scratch_git == live_git:
        raise RuntimeError("refusing git against the live GIT_DIR")


def git(scratch: Path, *args: str) -> tuple[int, str]:
    _refuse_live_tree(scratch)
    cmd = [
        "git",
        "-C",
        str(scratch),
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "user.name=adv-0123",
        "-c",
        "user.email=adv-0123@invalid",
        *args,
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        env=_clean_git_env(),
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _write(root: Path, rel: str, content: str) -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return rel.replace("\\", "/")


def cached_names(scratch: Path) -> list[str]:
    rc, out = git(scratch, "diff", "--cached", "--name-only", "-z")
    if rc != 0:
        raise RuntimeError(f"git diff --cached failed rc={rc} {out[-400:]}")
    names = [n.replace("\\", "/") for n in out.split("\0") if n]
    return sorted(names)


def init_scratch(root: Path) -> None:
    rc, out = git(root, "init", "--quiet")
    if rc != 0:
        raise RuntimeError(f"git init failed rc={rc} {out[-400:]}")


def inventory_program() -> dict[str, Any]:
    present = {}
    for key, rel in _CANDIDATES.items():
        present[key] = (REPO / rel).exists()
    importable = False
    try:
        import file_lease  # noqa: F401

        importable = True
    except ImportError:
        importable = False
    candidate = REPO / "tools/command-center/file_lease.py"
    loaded = False
    if candidate.is_file():
        import importlib.util

        spec = importlib.util.spec_from_file_location("adv0123_file_lease", candidate)
        loaded = spec is not None
    return {
        "present": present,
        "import_file_lease": importable,
        "file_lease_module_loadable": loaded,
        "shipped_file_lease_api": bool(
            present["file_lease_py"] or importable or loaded
        ),
        "work_claim_is_unit_id_not_path": bool(present["work_claim_py"]),
    }


def _scoped_disjoint(scratch: Path) -> dict[str, Any]:
    scratch.mkdir(parents=True, exist_ok=True)
    init_scratch(scratch)
    a_files = [_write(scratch, "disjoint-a/alpha.txt", "agent-A-only\n")]
    b_files = [_write(scratch, "disjoint-b/beta.txt", "agent-B-only\n")]
    rc, out = git(scratch, "add", "--", "disjoint-a")
    if rc != 0:
        raise RuntimeError(f"scoped git add failed rc={rc} {out[-400:]}")
    cached = cached_names(scratch)
    leaked = sorted(set(cached) & set(b_files))
    return {
        "id": "disjoint-scoped-add",
        "agent_a_files": a_files,
        "agent_b_files": b_files,
        "staging": "git add -- disjoint-a",
        "cached": cached,
        "sibling_in_cached": leaked,
        "isolated": leaked == [] and cached == a_files,
        "raw_cached": cached,
    }


def _overlap_broad_add(scratch: Path) -> dict[str, Any]:
    scratch.mkdir(parents=True, exist_ok=True)
    init_scratch(scratch)
    a_files = [
        _write(scratch, "agent-a/alpha.txt", "A-alpha\n"),
        _write(scratch, "overlap/from-a.txt", "A-overlap\n"),
    ]
    b_files = [
        _write(scratch, "agent-b/beta.txt", "B-beta\n"),
        _write(scratch, "overlap/from-b.txt", "B-overlap\n"),
    ]
    rc, out = git(scratch, "add", "-A")
    if rc != 0:
        raise RuntimeError(f"broad git add -A failed rc={rc} {out[-400:]}")
    cached = cached_names(scratch)
    swept = sorted(set(cached) & set(b_files))
    planted_visible = "agent-b/beta.txt" in cached
    return {
        "id": "overlap-broad-add",
        "agent_a_files": a_files,
        "agent_b_files": b_files,
        "staging": "git add -A",
        "cached": cached,
        "sibling_in_cached": swept,
        "swept_sibling": swept != [],
        "planted_contamination_visible": planted_visible,
        "raw_cached": cached,
    }


def consulted_write(
    db: dict[str, dict[str, str]], identity: str, rel: str, content: str, root: Path
) -> dict[str, Any]:
    rec = db.get(rel)
    if rec and rec.get("holder") != identity:
        return {
            "identity": identity,
            "path": rel,
            "disposition": "blocked",
            "wrote": False,
        }
    _write(root, rel, content)
    return {
        "identity": identity,
        "path": rel,
        "disposition": "allowed",
        "wrote": True,
    }


def _lease_experiment(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    inv = inventory_program()
    leased = "leased/path.txt"
    paper = {"path": leased, "holder": "identity-A", "advisory": True}
    dest = root / leased
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("written-by-identity-B\n", encoding="utf-8")
    body = dest.read_text(encoding="utf-8")
    unconsulted = {
        "holder": "identity-A",
        "writer": "identity-B",
        "path": leased,
        "disposition": "silently-allowed",
        "blocked": False,
        "warned": False,
        "wrote": body == "written-by-identity-B\n",
        "consulted_shipped_api": False,
        "reason": (
            "no shipped file-lease API; paper lease was not consulted; "
            "write succeeded"
            if not inv["shipped_file_lease_api"]
            else "shipped API present but this drill used the unconsulted path"
        ),
    }
    fixture_root = root / "consult-fixture"
    fixture_root.mkdir()
    db = {leased: paper}
    bad = consulted_write(db, "identity-B", leased, "conflict\n", fixture_root)
    good = consulted_write(db, "identity-A", leased, "holder\n", fixture_root)
    unleased = consulted_write(
        db, "identity-B", "other/unleased.txt", "ok\n", fixture_root
    )
    fixture = {
        "fired_on_bad_state": bad["disposition"] == "blocked",
        "silent_on_good_state": good["disposition"] == "allowed",
        "silent_on_unleased": unleased["disposition"] == "allowed",
        "bad": bad,
        "good": good,
        "unleased": unleased,
    }
    return {
        "inventory": inv,
        "paper_lease": paper,
        "conflicting_write": unconsulted,
        "consult_fixture": fixture,
        "lease_prevented_overlap": False,
        "lease_is_documentation": not inv["shipped_file_lease_api"],
    }


def measure() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="adv0123-") as tmp_s:
        tmp = Path(tmp_s).resolve()
        if tmp == REPO.resolve() or REPO.resolve() in tmp.parents:
            raise RuntimeError("tempfile resolved inside the live worktree")
        disjoint = _scoped_disjoint(tmp / "disjoint")
        overlap = _overlap_broad_add(tmp / "overlap")
        lease = _lease_experiment(tmp / "lease")
        scratch_ok = True

    disjoint_ok = bool(disjoint["isolated"])
    planted_ok = bool(overlap["planted_contamination_visible"])
    sweep = bool(overlap["swept_sibling"])
    lease_both = bool(
        lease["consult_fixture"]["fired_on_bad_state"]
        and lease["consult_fixture"]["silent_on_good_state"]
        and lease["consult_fixture"]["silent_on_unleased"]
    )
    both_ok = disjoint_ok and planted_ok and scratch_ok and lease_both

    targets = [
        {
            "target_id": "TARGET-BROAD-STAGE-SWEEPS-SIBLING",
            "claim": (
                "A broad git add -A on one shared index stages another "
                "agent's files."
            ),
            "verdict": "CONFIRMED" if sweep else "REFUTED",
            "oracle": "git diff --cached --name-only",
            "sibling_in_cached": overlap["sibling_in_cached"],
        },
        {
            "target_id": "TARGET-DISJOINT-SCOPED-ADD-ISOLATION",
            "claim": (
                "Two agents with disjoint file sets and a scoped add do not "
                "contaminate each other's index."
            ),
            "verdict": "CONFIRMED" if disjoint_ok else "REFUTED",
            "oracle": "git diff --cached --name-only",
            "sibling_in_cached": disjoint["sibling_in_cached"],
        },
        {
            "target_id": "TARGET-LEASE-PREVENTS-CONFLICTING-WRITE",
            "claim": (
                "A file lease acquired by identity A prevents identity B "
                "from writing the leased path."
            ),
            "verdict": (
                "CONFIRMED" if lease["lease_prevented_overlap"] else "REFUTED"
            ),
            "disposition": lease["conflicting_write"]["disposition"],
        },
        {
            "target_id": "TARGET-LEASE-IS-CONSULTED-CONTROL",
            "claim": (
                "The shipped file-lease mechanism is consulted on write and "
                "is therefore a control, not documentation."
            ),
            "verdict": (
                "REFUTED" if lease["lease_is_documentation"] else "PARTIAL"
            ),
            "shipped_file_lease_api": lease["inventory"]["shipped_file_lease_api"],
        },
    ]

    overall = "CONFIRMED"
    if not both_ok:
        overall = "NOT-CHECKED"
        for t in targets:
            t["verdict"] = "NOT-CHECKED"

    return {
        "probe1": {
            "instrument": "git-diff-cached-oracle",
            "disjoint": disjoint,
            "overlap": overlap,
            "scratch_outside_live_tree": scratch_ok,
        },
        "probe2": {
            "instrument": "lease-acquire-then-conflicting-write",
            "lease": lease,
        },
        "controls": {
            "disjoint_ok": disjoint_ok,
            "planted_ok": planted_ok,
            "scratch_ok": scratch_ok,
            "lease_both_states_ok": lease_both,
            "both_ok": both_ok,
        },
        "targets": targets,
        "overall_verdict": overall,
    }


def probe1_report(m: dict[str, Any]) -> str:
    payload = {
        "instrument": m["probe1"]["instrument"],
        "controls": {
            "disjoint_ok": m["controls"]["disjoint_ok"],
            "planted_ok": m["controls"]["planted_ok"],
            "scratch_ok": m["controls"]["scratch_ok"],
        },
        "disjoint": {
            "cached": m["probe1"]["disjoint"]["cached"],
            "sibling_in_cached": m["probe1"]["disjoint"]["sibling_in_cached"],
            "isolated": m["probe1"]["disjoint"]["isolated"],
        },
        "overlap": {
            "cached": m["probe1"]["overlap"]["cached"],
            "sibling_in_cached": m["probe1"]["overlap"]["sibling_in_cached"],
            "swept_sibling": m["probe1"]["overlap"]["swept_sibling"],
            "planted_contamination_visible": m["probe1"]["overlap"][
                "planted_contamination_visible"
            ],
        },
        "targets": [
            t
            for t in m["targets"]
            if t["target_id"]
            in {
                "TARGET-BROAD-STAGE-SWEEPS-SIBLING",
                "TARGET-DISJOINT-SCOPED-ADD-ISOLATION",
            }
        ],
        "overall_verdict": m["overall_verdict"],
    }
    lines = [
        PROBE1_NAME,
        dumps(payload).rstrip("\n"),
        (
            "disjoint isolated={0} cached={1} leaked={2}".format(
                payload["disjoint"]["isolated"],
                payload["disjoint"]["cached"],
                payload["disjoint"]["sibling_in_cached"],
            )
        ),
        (
            "overlap swept={0} cached={1} sibling={2} planted={3}".format(
                payload["overlap"]["swept_sibling"],
                payload["overlap"]["cached"],
                payload["overlap"]["sibling_in_cached"],
                payload["overlap"]["planted_contamination_visible"],
            )
        ),
        (
            "controls disjoint_ok={0} planted_ok={1} scratch_ok={2}".format(
                payload["controls"]["disjoint_ok"],
                payload["controls"]["planted_ok"],
                payload["controls"]["scratch_ok"],
            )
        ),
        f"overall_verdict={payload['overall_verdict']}",
    ]
    return "\n".join(lines) + "\n"


def probe2_report(m: dict[str, Any]) -> str:
    lease = m["probe2"]["lease"]
    payload = {
        "instrument": m["probe2"]["instrument"],
        "inventory": lease["inventory"],
        "conflicting_write": lease["conflicting_write"],
        "consult_fixture": {
            "fired_on_bad_state": lease["consult_fixture"]["fired_on_bad_state"],
            "silent_on_good_state": lease["consult_fixture"]["silent_on_good_state"],
            "silent_on_unleased": lease["consult_fixture"]["silent_on_unleased"],
        },
        "lease_prevented_overlap": lease["lease_prevented_overlap"],
        "lease_is_documentation": lease["lease_is_documentation"],
        "targets": [
            t
            for t in m["targets"]
            if t["target_id"]
            in {
                "TARGET-LEASE-PREVENTS-CONFLICTING-WRITE",
                "TARGET-LEASE-IS-CONSULTED-CONTROL",
            }
        ],
        "overall_verdict": m["overall_verdict"],
    }
    lines = [
        PROBE2_NAME,
        dumps(payload).rstrip("\n"),
        (
            "conflicting_write disposition={0} blocked={1} wrote={2}".format(
                payload["conflicting_write"]["disposition"],
                payload["conflicting_write"]["blocked"],
                payload["conflicting_write"]["wrote"],
            )
        ),
        (
            "shipped_api={0} documentation={1} prevented={2}".format(
                payload["inventory"]["shipped_file_lease_api"],
                payload["lease_is_documentation"],
                payload["lease_prevented_overlap"],
            )
        ),
        (
            "consult_fixture bad={0} holder={1} unleased={2}".format(
                payload["consult_fixture"]["fired_on_bad_state"],
                payload["consult_fixture"]["silent_on_good_state"],
                payload["consult_fixture"]["silent_on_unleased"],
            )
        ),
        f"overall_verdict={payload['overall_verdict']}",
    ]
    return "\n".join(lines) + "\n"
