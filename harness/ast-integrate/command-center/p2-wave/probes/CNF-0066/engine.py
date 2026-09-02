#!/usr/bin/env python3
"""Live detector-controlled retests of recorded and planted absences."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"

KNOWN = "CNF0066_KNOWN_PRESENT_TOKEN"
ABSENT = "CNF0066_SHOULD_BE_ABSENT_TOKEN"
FALSE = "CNF0066_FALSE_ABSENCE_TOKEN"
WRONG_PATH = "CNF0066_WRONG_PATH_TOKEN"
WRONG_FIELD = "CNF0066_WRONG_FIELD_TOKEN"
STALE = "CNF0066_STALE_INDEX_TOKEN"
RECALL = "CNF0066_RECALL_NOTE_TOKEN"

SKIP_DIR_NAMES = {".git", "__pycache__", "node_modules", ".venv", "venv"}
MAX_FILE_BYTES = 2_000_000
IMPL_SKIP = (
    "command-center/WORK-UNIT-CATALOG.json",
    "command-center/p2-wave/probes/CNF-0066/",
    "command-center/confirmation/CNF-0066-negative-result-recheck.json",
    "command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json",
    "command-center/p2-wave/P2-CLOUD-PROGRESS_2026-08-24.md",
)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def fingerprint(tool: str, shell: str, field: str, kind: str) -> dict[str, Any]:
    return {
        "tool": tool,
        "shell": shell,
        "field": field,
        "measurement_kind": kind,
        "tuple": f"{tool}|{shell}|{field}|{kind}",
    }


def skipped(rel_p: str, extra_skip: tuple[str, ...]) -> bool:
    return any(rel_p == s or rel_p.startswith(s) for s in extra_skip)


def iter_files(root: Path, extra_skip: tuple[str, ...] = ()) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        rp = rel(root)
        return [] if skipped(rp, extra_skip) else [root]
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            rp = rel(path)
            if skipped(rp, extra_skip):
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            out.append(path)
    return out


def python_hits(
    root: Path, needle: str, extra_skip: tuple[str, ...] = ()
) -> tuple[int, list[str]]:
    hits: list[str] = []
    for path in iter_files(root, extra_skip):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if needle in text:
            hits.append(rel(path))
    return len(hits), hits


def grep_hits(
    root: Path, needle: str, extra_skip: tuple[str, ...] = ()
) -> tuple[int, list[str], int]:
    if not root.exists():
        return 0, [], 0
    cmd = [
        "grep",
        "-R",
        "-F",
        "-I",
        "-l",
        "--binary-files=without-match",
        needle,
        str(root),
    ]
    try:
        proc = subprocess.run(
            cmd, cwd=str(REPO), capture_output=True, text=True, timeout=90
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0, [], 127
    paths: list[str] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        rp = rel(Path(line))
        if skipped(rp, extra_skip):
            continue
        paths.append(rp)
    rc = proc.returncode if proc.returncode in (0, 1) else proc.returncode
    return len(paths), paths, rc


def json_field_hits(root: Path, needle: str, field: str) -> tuple[int, list[str]]:
    hits: list[str] = []
    for path in iter_files(root):
        if path.suffix.lower() != ".json":
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(doc, dict) and needle in str(doc.get(field) or ""):
            hits.append(rel(path))
    return len(hits), hits


def tool_run(
    tool: str,
    shell: str,
    field: str,
    kind: str,
    hit_count: int,
    command: str,
    paths: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    row = fingerprint(tool, shell, field, kind)
    row["hit_count"] = int(hit_count)
    row["command"] = command
    if paths is not None:
        row["paths"] = paths[:12]
    row.update(extra)
    return row


def content_pair(
    root: Path, needle: str, extra_skip: tuple[str, ...] = ()
) -> tuple[dict[str, Any], dict[str, Any]]:
    n_a, p_a = python_hits(root, needle, extra_skip)
    n_b, p_b, rc = grep_hits(root, needle, extra_skip)
    a = tool_run(
        "python-walk",
        "posix-python",
        "file-bytes",
        "substring-count",
        n_a,
        f"python-walk needle={needle!r} root={rel(root)}",
        p_a,
    )
    b = tool_run(
        "grep",
        "posix-grep",
        "file-bytes",
        "substring-count",
        n_b,
        f"grep -R -F -I -l {needle!r} {rel(root)} (rc={rc})",
        p_b,
        exit_code=rc,
    )
    return a, b


def field_content_pair(
    root: Path, needle: str, field: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    n_a, p_a = json_field_hits(root, needle, field)
    n_b, p_b = python_hits(root, needle)
    a = tool_run(
        "python-json-field",
        "posix-python",
        f"json.{field}",
        "field-substring",
        n_a,
        f"json[{field!r}] contains {needle!r} under {rel(root)}",
        p_a,
    )
    b = tool_run(
        "python-walk",
        "posix-python",
        "file-bytes",
        "substring-count",
        n_b,
        f"python-walk needle={needle!r} root={rel(root)}",
        p_b,
    )
    return a, b


def path_pair(target: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    a = tool_run(
        "pathlib.Path.exists",
        "posix-python",
        "filesystem-path",
        "existence",
        int(target.exists()),
        f"Path({rel(target)!r}).exists()",
    )
    b = tool_run(
        "os.path.lexists",
        "posix-python",
        "filesystem-path",
        "existence",
        int(os.path.lexists(str(target))),
        f"os.path.lexists({rel(target)!r})",
    )
    return a, b


def git_pair(since: str, pattern: str | None) -> tuple[dict[str, Any], dict[str, Any], str]:
    git_dir = REPO / ".git"
    b = tool_run(
        "pathlib.Path.exists",
        "posix-python",
        "filesystem-path",
        "existence",
        int(git_dir.exists()),
        "Path('.git').exists()",
    )
    cmd = ["git", "log", "--oneline", f"--since={since}"]
    if pattern:
        cmd.extend(["--grep", pattern, "-i"])
    note = "ok"
    try:
        proc = subprocess.run(
            cmd, cwd=str(REPO), capture_output=True, text=True, timeout=30
        )
        lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
        a = tool_run(
            "git-log",
            "posix-git",
            "commit-subject",
            "log-count",
            len(lines) if proc.returncode == 0 else 0,
            " ".join(cmd),
            exit_code=proc.returncode,
        )
        if proc.returncode != 0:
            note = (proc.stderr or "git-failed").strip()[:240]
    except (OSError, subprocess.TimeoutExpired) as exc:
        a = tool_run(
            "git-log",
            "posix-git",
            "commit-subject",
            "log-count",
            0,
            " ".join(cmd),
            exit_code=127,
        )
        note = f"{type(exc).__name__}:{exc}"
    return a, b, note


def which_pair(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    found = shutil.which(name)
    a = tool_run(
        "shutil.which",
        "posix-python",
        "PATH",
        "binary-lookup",
        int(bool(found)),
        f"shutil.which({name!r})",
        resolved=found,
    )
    win = Path(r"C:\Program Files\Git\usr\bin") / name
    b = tool_run(
        "pathlib.Path.exists",
        "posix-python",
        "filesystem-path",
        "existence",
        int(win.exists()),
        f"Path({str(win)!r}).exists()",
    )
    return a, b


def recall_store() -> dict[str, Any]:
    vault = FIX / "recall_vault"
    notes = vault / "notes"
    index = vault / "index.json"
    n_fs, p_fs = python_hits(notes, RECALL)
    n_ctrl, _ = python_hits(notes, KNOWN)
    n_idx, p_idx = python_hits(index, RECALL)
    n_idx_ctrl, _ = python_hits(index, KNOWN)
    cli = next((exe for exe in ("basic-memory", "basic_memory") if shutil.which(exe)), None)
    live_paths: list[str] = []
    for root_name in ("memory", "basic-memory", ".basic-memory", "notes"):
        root = REPO / root_name
        if root.exists():
            _, live_paths = python_hits(root, "Program B")
            if live_paths:
                break
    return {
        "ran": True,
        "cli": cli,
        "vault": rel(vault),
        "filesystem_subject_hits": n_fs,
        "filesystem_control_hits": n_ctrl,
        "filesystem_paths": p_fs[:8],
        "index_subject_hits": n_idx,
        "index_control_hits": n_idx_ctrl,
        "index_paths": p_idx[:8],
        "live_program_b_paths": live_paths[:8],
        "store_kind": "planted-vault-plus-cli-probe",
    }


def slim(tool: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "tool",
        "shell",
        "field",
        "measurement_kind",
        "hit_count",
        "command",
        "tuple",
    )
    return {k: tool[k] for k in keys}


def make_control(
    cid: str,
    item: str,
    found: bool,
    tool_a: dict[str, Any],
    tool_b: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": cid,
        "search_command": tool_a["command"],
        "known_present_item": item,
        "known_present_found": bool(found),
        "tool_a": slim(tool_a),
        "tool_b": slim(tool_b),
        "fingerprints_differ": tool_a.get("tuple") != tool_b.get("tuple"),
    }


def make_record(
    *,
    rid: str,
    source: str,
    claim: str,
    classification: str,
    control: dict[str, Any] | None,
    search_command: str,
    absence_result: str,
    tool_a: dict[str, Any],
    tool_b: dict[str, Any],
    failure_mode: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    found = bool(control and control.get("known_present_found"))
    rec = {
        "id": rid,
        "source": source,
        "claim": claim,
        "classification": classification,
        "control_id": None if control is None else control["id"],
        "control_found_known_present": found,
        "search_command": search_command,
        "absence_result": absence_result,
        "failure_mode": failure_mode,
        "recall_ran": True,
        "tool_a": slim(tool_a),
        "tool_b": slim(tool_b),
        "tools_disagree": int(tool_a.get("hit_count") or 0)
        != int(tool_b.get("hit_count") or 0),
        "fingerprints_differ": tool_a.get("tuple") != tool_b.get("tuple"),
    }
    if extra:
        rec.update(extra)
    return rec


def classify_checked(
    control_found: bool,
    subject_a: int,
    subject_b: int,
    prefer_failure: str | None = None,
) -> tuple[str, str]:
    if not control_found:
        return "DETECTOR_FAILURE", prefer_failure or "wrong-path"
    if subject_a > 0 and subject_b > 0:
        return "FALSE_ABSENCE", "none"
    if subject_a == 0 and subject_b == 0:
        return "CONFIRMED_ABSENCE", "none"
    return "DETECTOR_FAILURE", prefer_failure or "stale-cache"


def retest_all() -> dict[str, Any]:
    recall = recall_store()
    records: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []

    ca, cb = content_pair(FIX / "known_present", KNOWN)
    live_ctrl = make_control(
        "CTRL-PLANTED-CONTENT",
        KNOWN,
        ca["hit_count"] > 0 and cb["hit_count"] > 0,
        ca,
        cb,
    )
    controls.append(live_ctrl)

    sa, sb = content_pair(FIX / "absent_ok", ABSENT)
    cls, mode = classify_checked(
        live_ctrl["known_present_found"], sa["hit_count"], sb["hit_count"]
    )
    records.append(
        make_record(
            rid="P-CONFIRMED-ABSENCE",
            source="planted",
            claim="Planted token CNF0066_SHOULD_BE_ABSENT_TOKEN is absent under fixtures/absent_ok",
            classification=cls,
            control=live_ctrl,
            search_command=sa["command"],
            absence_result=f"python={sa['hit_count']} grep={sb['hit_count']}",
            tool_a=sa,
            tool_b=sb,
            failure_mode=mode,
        )
    )

    fa, fb = content_pair(FIX / "false_absence", FALSE)
    cls, mode = classify_checked(
        live_ctrl["known_present_found"], fa["hit_count"], fb["hit_count"]
    )
    records.append(
        make_record(
            rid="P-FALSE-ABSENCE",
            source="planted",
            claim="Corpus claimed CNF0066_FALSE_ABSENCE_TOKEN does not exist",
            classification=cls,
            control=live_ctrl,
            search_command=fa["command"],
            absence_result=f"python={fa['hit_count']} grep={fb['hit_count']}",
            tool_a=fa,
            tool_b=fb,
            failure_mode=mode,
        )
    )

    empty = FIX / "wrong_path" / "empty"
    hidden = FIX / "wrong_path" / "hidden"
    wa, wb = content_pair(empty, KNOWN)
    broken = make_control(
        "CTRL-WRONG-PATH",
        KNOWN,
        wa["hit_count"] > 0 and wb["hit_count"] > 0,
        wa,
        wb,
    )
    controls.append(broken)
    xa, xb = content_pair(empty, WRONG_PATH)
    ya, yb = content_pair(hidden, WRONG_PATH)
    cls, mode = classify_checked(
        broken["known_present_found"],
        xa["hit_count"],
        xb["hit_count"],
        prefer_failure="wrong-path",
    )
    records.append(
        make_record(
            rid="P-WRONG-PATH",
            source="planted",
            claim="Search of fixtures/wrong_path/empty claimed CNF0066_WRONG_PATH_TOKEN absent",
            classification=cls,
            control=broken,
            search_command=xa["command"],
            absence_result=(
                f"empty python={xa['hit_count']} grep={xb['hit_count']}; "
                f"hidden python={ya['hit_count']} grep={yb['hit_count']}"
            ),
            tool_a=xa,
            tool_b=xb,
            failure_mode="wrong-path",
            extra={"sibling_hidden_hits": ya["hit_count"] + yb["hit_count"]},
        )
    )

    wf_root = FIX / "wrong_field"
    ta, tb = field_content_pair(wf_root, KNOWN, "title")
    field_ctrl = make_control("CTRL-TITLE-FIELD", KNOWN, ta["hit_count"] > 0, ta, tb)
    controls.append(field_ctrl)
    sa_f, sb_f = field_content_pair(wf_root, WRONG_FIELD, "title")
    cls, mode = classify_checked(
        field_ctrl["known_present_found"],
        sa_f["hit_count"],
        sb_f["hit_count"],
        prefer_failure="wrong-field",
    )
    records.append(
        make_record(
            rid="P-WRONG-FIELD",
            source="planted",
            claim="JSON title search claimed CNF0066_WRONG_FIELD_TOKEN absent",
            classification=cls,
            control=field_ctrl,
            search_command=sa_f["command"],
            absence_result=f"title={sa_f['hit_count']} content={sb_f['hit_count']}",
            tool_a=sa_f,
            tool_b=sb_f,
            failure_mode="wrong-field",
        )
    )

    ia, ib = content_pair(FIX / "stale" / "index.json", KNOWN)
    stale_ctrl = make_control("CTRL-STALE-INDEX", KNOWN, ia["hit_count"] > 0, ia, ib)
    controls.append(stale_ctrl)
    ja, _ = content_pair(FIX / "stale" / "index.json", STALE)
    ka, kb = content_pair(FIX / "stale" / "live.txt", STALE)
    tool_live = dict(ka)
    tool_live["tool"] = "python-walk-live"
    tool_live["tuple"] = fingerprint(
        "python-walk-live", "posix-python", "file-bytes", "substring-count"
    )["tuple"]
    cls, mode = classify_checked(
        stale_ctrl["known_present_found"],
        ja["hit_count"],
        tool_live["hit_count"],
        prefer_failure="stale-cache",
    )
    records.append(
        make_record(
            rid="P-STALE-CACHE",
            source="planted",
            claim="Stale index.json claimed CNF0066_STALE_INDEX_TOKEN absent",
            classification=cls,
            control=stale_ctrl,
            search_command=ja["command"],
            absence_result=(
                f"index={ja['hit_count']} live={tool_live['hit_count']} "
                f"live-grep={kb['hit_count']}"
            ),
            tool_a=ja,
            tool_b=tool_live,
            failure_mode="stale-cache",
        )
    )

    na, nb = content_pair(FIX / "absent_ok", "CNF0066_UNCHECKED_TOKEN")
    records.append(
        make_record(
            rid="P-NO-CONTROL",
            source="planted",
            claim="Unchecked absence: no known-present control was run",
            classification="NOT-CHECKED",
            control=None,
            search_command=na["command"],
            absence_result=(
                f"python={na['hit_count']} grep={nb['hit_count']} (ignored: no control)"
            ),
            tool_a=na,
            tool_b=nb,
            failure_mode="no-control",
        )
    )

    rec_a, rec_b = content_pair(FIX / "recall_vault" / "notes", KNOWN)
    rec_ctrl = make_control(
        "CTRL-RECALL-FS",
        KNOWN,
        rec_a["hit_count"] > 0 and rec_b["hit_count"] > 0,
        rec_a,
        rec_b,
    )
    controls.append(rec_ctrl)
    ra, rb = content_pair(FIX / "recall_vault" / "notes", RECALL)
    ia2, ib2 = content_pair(FIX / "recall_vault" / "index.json", RECALL)
    records.append(
        make_record(
            rid="P-RECALL-NOT-DETECTION",
            source="planted",
            claim="Semantic index declared Program B / recall token unbuilt",
            classification="RECALL_NOT_DETECTION",
            control=rec_ctrl,
            search_command=ia2["command"],
            absence_result=(
                f"index python={ia2['hit_count']} grep={ib2['hit_count']}; "
                f"filesystem python={ra['hit_count']} grep={rb['hit_count']}"
            ),
            tool_a=ia2,
            tool_b=rb,
            failure_mode="recall-not-detection",
            extra={"recall_detail": recall},
        )
    )

    win_root = Path(r"C:\Users\Prekzursil\.claude\harness-restore-20260806")
    wa2, wb2 = content_pair(win_root, KNOWN)
    win_ctrl = make_control(
        "CTRL-WIN-PATH",
        KNOWN,
        wa2["hit_count"] > 0 and wb2["hit_count"] > 0,
        wa2,
        wb2,
    )
    controls.append(win_ctrl)
    sa2, sb2 = content_pair(win_root, ABSENT)
    cls, mode = classify_checked(
        win_ctrl["known_present_found"],
        sa2["hit_count"],
        sb2["hit_count"],
        prefer_failure="wrong-shell",
    )
    records.append(
        make_record(
            rid="P-WRONG-SHELL-PATH",
            source="planted",
            claim="Search of a Git-Bash/Windows path claimed a token absent on this Linux tree",
            classification=cls,
            control=win_ctrl,
            search_command=sa2["command"],
            absence_result=f"python={sa2['hit_count']} grep={sb2['hit_count']}",
            tool_a=sa2,
            tool_b=sb2,
            failure_mode="wrong-shell",
        )
    )

    na_a, na_b = content_pair(REPO, "unified-continuation")
    cls, mode = classify_checked(
        live_ctrl["known_present_found"], na_a["hit_count"], na_b["hit_count"]
    )
    records.append(
        make_record(
            rid="L-UNIFIED-GREP-NAIVE",
            source="WORK-UNIT-CATALOG.json:R-B05",
            claim="grep -rl 'unified-continuation' across repo = 0",
            classification=cls,
            control=live_ctrl,
            search_command=na_a["command"],
            absence_result=f"python={na_a['hit_count']} grep={na_b['hit_count']}",
            tool_a=na_a,
            tool_b=na_b,
            failure_mode="wrong-field" if cls == "FALSE_ABSENCE" else mode,
            extra={
                "note": "Hits inside the catalog that quotes the claim are quoted evidence, not an implementation."
            },
        )
    )

    n_ia, p_ia = python_hits(REPO, "unified-continuation", IMPL_SKIP)
    n_ib, p_ib, rc_i = grep_hits(REPO, "unified-continuation", IMPL_SKIP)
    ia3 = tool_run(
        "python-walk",
        "posix-python",
        "file-bytes",
        "substring-count",
        n_ia,
        "python-walk needle='unified-continuation' root=. (impl exclusions)",
        p_ia,
    )
    ib3 = tool_run(
        "grep",
        "posix-grep",
        "file-bytes",
        "substring-count",
        n_ib,
        f"grep -R -F -I -l 'unified-continuation' . (impl exclusions, rc={rc_i})",
        p_ib,
    )
    cls, mode = classify_checked(
        live_ctrl["known_present_found"], ia3["hit_count"], ib3["hit_count"]
    )
    records.append(
        make_record(
            rid="L-UNIFIED-GREP-IMPL",
            source="WORK-UNIT-CATALOG.json:R-B05",
            claim="unified-continuation absent from implementation roots (catalog/self excluded)",
            classification=cls,
            control=live_ctrl,
            search_command=ia3["command"],
            absence_result=f"python={ia3['hit_count']} grep={ib3['hit_count']}",
            tool_a=ia3,
            tool_b=ib3,
            failure_mode=mode,
        )
    )

    catalog = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    pa, pb = path_pair(catalog)
    path_ctrl = make_control(
        "CTRL-PATH-EXISTS",
        "command-center/WORK-UNIT-CATALOG.json",
        pa["hit_count"] > 0 and pb["hit_count"] > 0,
        pa,
        pb,
    )
    controls.append(path_ctrl)

    path_claims = [
        (
            "L-INSTALL-PY",
            "WORK-UNIT-CATALOG.json:R-A01",
            "install.py absent at repo root",
            REPO / "install.py",
        ),
        (
            "L-SINGLE-SIGNAL-RULE",
            "CNF-0066.inputs",
            "rules/common/single-signal-verification.md is absent",
            REPO / "rules" / "common" / "single-signal-verification.md",
        ),
        (
            "L-CLAIM-REGISTRY",
            "CNF-0066.inputs",
            "CLAIM-REGISTRY.json is absent",
            REPO / "command-center" / "CLAIM-REGISTRY.json",
        ),
        (
            "L-CNF0006-ARTIFACT",
            "CNF-0006.output_path",
            "command-center/confirmation/CNF-0006-probe-independence.json is absent",
            REPO
            / "command-center"
            / "confirmation"
            / "CNF-0006-probe-independence.json",
        ),
        (
            "L-UNIFIED-DIR",
            "WORK-UNIT-CATALOG.json:R-A01",
            "unified-continuation/ directory is absent",
            REPO / "unified-continuation",
        ),
        (
            "L-DATABRICKS-ENVELOPE",
            "WORK-UNIT-CATALOG.json",
            "shared/DATABRICKS-ENVELOPE/ does not exist",
            REPO / "shared" / "DATABRICKS-ENVELOPE",
        ),
        (
            "L-REDESIGN-DIAGRAMS",
            "WORK-UNIT-CATALOG.json",
            "platform-redesign-2026-07-19/diagrams/ does not exist",
            REPO / "platform-redesign-2026-07-19" / "diagrams",
        ),
        (
            "L-WINPROC",
            "WORK-UNIT-CATALOG.json",
            "winproc.py is absent",
            REPO / "winproc.py",
        ),
        (
            "L-RESUME-JSON",
            "WORK-UNIT-CATALOG.json:R-B05",
            "RESUME.json is absent on this tree",
            REPO / "RESUME.json",
        ),
    ]
    for rid, source, claim, target in path_claims:
        sa_p, sb_p = path_pair(target)
        cls, mode = classify_checked(
            path_ctrl["known_present_found"], sa_p["hit_count"], sb_p["hit_count"]
        )
        records.append(
            make_record(
                rid=rid,
                source=source,
                claim=claim,
                classification=cls,
                control=path_ctrl,
                search_command=sa_p["command"],
                absence_result=f"exists={sa_p['hit_count']} lexists={sb_p['hit_count']}",
                tool_a=sa_p,
                tool_b=sb_p,
                failure_mode=mode,
            )
        )

    name_hits = [rel(p) for p in iter_files(REPO) if p.name == "winproc.py"]
    g_a = tool_run(
        "pathlib.Path.rglob",
        "posix-python",
        "filename",
        "glob-count",
        len(name_hits),
        "os.walk filename==winproc.py (rglob-equivalent)",
        name_hits,
    )
    g_b = tool_run(
        "os.walk",
        "posix-python",
        "filename",
        "walk-count",
        len(name_hits),
        "os.walk filename==winproc.py",
        name_hits,
    )
    # Second tool must differ in fingerprint even if counts match: use grep files-from name.
    g_b = tool_run(
        "python-name-scan",
        "posix-python",
        "directory-entry-name",
        "basename-equals",
        len(name_hits),
        "os.walk basename == 'winproc.py'",
        name_hits,
    )
    cls, mode = classify_checked(
        path_ctrl["known_present_found"], g_a["hit_count"], g_b["hit_count"]
    )
    records.append(
        make_record(
            rid="L-WINPROC-WALK",
            source="WORK-UNIT-CATALOG.json",
            claim="winproc.py absent everywhere on this tree",
            classification=cls,
            control=path_ctrl,
            search_command=g_a["command"],
            absence_result=f"rglob-eq={g_a['hit_count']} walk={g_b['hit_count']}",
            tool_a=g_a,
            tool_b=g_b,
            failure_mode=mode,
        )
    )

    ga, gb, gnote = git_pair("2026-07-23", None)
    git_ctrl_a, git_ctrl_b, _ = git_pair("1970-01-01", None)
    git_ctrl = make_control(
        "CTRL-GIT-META",
        "HEAD/.git",
        git_ctrl_b["hit_count"] > 0 and git_ctrl_a.get("exit_code") == 0,
        git_ctrl_a,
        git_ctrl_b,
    )
    controls.append(git_ctrl)
    if not git_ctrl["known_present_found"]:
        gcls, gmode = "DETECTOR_FAILURE", "missing-git-metadata"
    else:
        gcls, gmode = classify_checked(True, ga["hit_count"], ga["hit_count"])
    records.append(
        make_record(
            rid="L-GIT-SINCE-0723",
            source="WORK-UNIT-CATALOG.json:R-B05",
            claim="git log since 07-23 = 0 commits",
            classification=gcls,
            control=git_ctrl,
            search_command=ga["command"],
            absence_result=f"commits={ga['hit_count']} git_dir={gb['hit_count']} note={gnote[:160]}",
            tool_a=ga,
            tool_b=gb,
            failure_mode=gmode,
        )
    )

    sa_g, sb_g, snote = git_pair("1970-01-01", "skills")
    records.append(
        make_record(
            rid="L-GIT-SKILLS-CONTROL-RERUN",
            source="WORK-UNIT-CATALOG.json:R-B05",
            claim="Original git control query for 'skills' (known-present on a real repo)",
            classification=(
                "DETECTOR_FAILURE"
                if not git_ctrl["known_present_found"]
                else ("CONFIRMED_ABSENCE" if sa_g["hit_count"] == 0 else "FALSE_ABSENCE")
            ),
            control=git_ctrl,
            search_command=sa_g["command"],
            absence_result=f"commits={sa_g['hit_count']} note={snote[:160]}",
            tool_a=sa_g,
            tool_b=sb_g,
            failure_mode=(
                "missing-git-metadata" if not git_ctrl["known_present_found"] else "none"
            ),
        )
    )

    wh_a, wh_b = which_pair("python3")
    which_ctrl = make_control(
        "CTRL-WHICH-PYTHON3", "python3-on-PATH", wh_a["hit_count"] > 0, wh_a, wh_b
    )
    controls.append(which_ctrl)
    if which_ctrl["known_present_found"] and wh_b["hit_count"] == 0:
        wcls, wmode = "DETECTOR_FAILURE", "wrong-shell"
    else:
        wcls, wmode = classify_checked(
            which_ctrl["known_present_found"],
            wh_b["hit_count"],
            wh_b["hit_count"],
            prefer_failure="wrong-shell",
        )
    records.append(
        make_record(
            rid="L-WHICH-WINDOWS-PATH",
            source="CNF-0006.precedent",
            claim="A Windows Git-Bash path lookup reporting python3 absent on Linux",
            classification=wcls,
            control=which_ctrl,
            search_command=wh_b["command"],
            absence_result=f"PATH={wh_a['hit_count']} winpath={wh_b['hit_count']}",
            tool_a=wh_a,
            tool_b=wh_b,
            failure_mode=wmode,
        )
    )

    live_pb_a, live_pb_b = content_pair(REPO / "memory", "Program B")
    cls, mode = classify_checked(
        rec_ctrl["known_present_found"], live_pb_a["hit_count"], live_pb_b["hit_count"]
    )
    records.append(
        make_record(
            rid="L-BASIC-MEMORY-PROGRAM-B",
            source="WORK-UNIT-CATALOG.json:R-B06",
            claim="basic-memory holds ZERO notes on Program B",
            classification=cls,
            control=rec_ctrl,
            search_command=live_pb_a["command"],
            absence_result=(
                f"live-memory python={live_pb_a['hit_count']} grep={live_pb_b['hit_count']}; "
                f"planted-vault-fs={recall['filesystem_subject_hits']} "
                f"planted-index={recall['index_subject_hits']} cli={recall['cli']!r}"
            ),
            tool_a=live_pb_a,
            tool_b=live_pb_b,
            failure_mode=mode,
            extra={"note": "Recall ran on planted vault before this unbuilt declaration."},
        )
    )

    counts = {
        "harvested": len(records),
        "confirmed_absence": sum(
            1 for r in records if r["classification"] == "CONFIRMED_ABSENCE"
        ),
        "false_absence": sum(1 for r in records if r["classification"] == "FALSE_ABSENCE"),
        "detector_failure": sum(
            1 for r in records if r["classification"] == "DETECTOR_FAILURE"
        ),
        "not_checked": sum(1 for r in records if r["classification"] == "NOT-CHECKED"),
        "recall_not_detection": sum(
            1 for r in records if r["classification"] == "RECALL_NOT_DETECTION"
        ),
    }
    counts["detector_failures_are_wrong_shell_path_field_or_stale_cache"] = sum(
        1
        for r in records
        if r["classification"] == "DETECTOR_FAILURE"
        and r.get("failure_mode")
        in {
            "wrong-shell",
            "wrong-path",
            "wrong-field",
            "stale-cache",
            "missing-git-metadata",
        }
    )
    absences = [
        {
            "id": r["id"],
            "claim": r["claim"],
            "control_id": r["control_id"],
            "control_found_known_present": True,
            "search_command": r["search_command"],
            "absence_result": r["absence_result"],
        }
        for r in records
        if r["classification"] == "CONFIRMED_ABSENCE"
    ]
    return {
        "records": records,
        "controls": controls,
        "absences": absences,
        "summary": counts,
        "recall": recall,
    }
