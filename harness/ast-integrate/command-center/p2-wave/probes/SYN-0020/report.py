"""Live docs-vs-code parity measurement for SYN-0020."""

from __future__ import annotations

from pathlib import Path

from contract import (
    EXPECTED_LIVE_DOCS,
    KNOWN_PRESENT_FIXTURE,
    KNOWN_PRESENT_SNIPPET,
    LIVE_CHECKLIST,
    MENTION_ONLY_FIXTURE,
    NEGATED_MENTION,
    P1,
    P2,
)
from extract import extract_many, extract_path
from runner import run_all
from statements import (
    classify_one,
    extract_statements,
    force_agree_without_test_id,
    is_archive_lf_blob_prescription,
    join_and_classify,
    validate_no_silent_agree,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def live_inventory() -> list[dict]:
    rows = []
    for rel in EXPECTED_LIVE_DOCS:
        path = REPO / rel
        rows.append(
            {
                "path": rel,
                "present": path.is_file() and path.stat().st_size > 0,
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return rows


def _unique(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def executable_paths() -> list[Path]:
    """Fenced commands that are safe to run: fixture docs only.

    Live README.md and RUNBOOK.md exist on this tree and contain
    git-clone / npm-install / close.py / seed.py --force. Those are
    inventoried, not executed.
    """
    paths: list[Path] = []
    docs = HERE / "fixtures" / "docs"
    if docs.is_dir():
        paths.extend(sorted(docs.glob("*.md")))
    return _unique(paths)


def statement_paths() -> list[Path]:
    paths: list[Path] = []
    checklist = REPO / LIVE_CHECKLIST
    if checklist.is_file():
        paths.append(checklist)
    docs = HERE / "fixtures" / "docs"
    if docs.is_dir():
        paths.extend(sorted(docs.glob("*.md")))
    for extra in (
        "untested.md",
        "noexec-marked.md",
        "known-present-git-archive.md",
        "mention-only.md",
    ):
        p = HERE / "fixtures" / extra
        if p.is_file():
            paths.append(p)
    return _unique(paths)


def corpus_paths() -> list[Path]:
    return statement_paths()


def noexec_both_states() -> dict:
    marked = HERE / "fixtures" / "noexec-marked.md"
    unmarked = HERE / "fixtures" / "noexec-unmarked.md"
    planted = "syn0020-noexec-planted-command"
    m = extract_path(marked, REPO)
    u = extract_path(unmarked, REPO)
    skipped = [c for c in m["skipped"] if planted in c["invocation"]]
    extracted = [c for c in u["commands"] if planted in c["invocation"]]
    leaked = [c for c in m["commands"] if planted in c["invocation"]]
    return {
        "planted": planted,
        "marked_skipped": len(skipped) == 1,
        "unmarked_extracted": len(extracted) == 1,
        "marked_did_not_leak": len(leaked) == 0,
        "pass": len(skipped) == 1 and len(extracted) == 1 and len(leaked) == 0,
        "marked_skip_reason": skipped[0]["skip_reason"] if skipped else None,
    }


def untested_control() -> dict:
    would_agree = "The hello token command always prints SYN-0020-readme-ok."
    forced = force_agree_without_test_id(would_agree)
    with_id = classify_one(
        would_agree, test_id="cmd-echo-readme", joined_exit=0, claimed_success=True
    )
    planted = classify_one(
        "The marketplace always ships a signed wheel on Tuesdays."
    )
    return {
        "forced_agree_without_test_id_verdict": forced["verdict"],
        "forced_agree_without_test_id_test_id": forced["test_id"],
        "rewrote_to_untested": forced["verdict"] == "UNTESTED" and not forced["test_id"],
        "with_test_id_verdict": with_id["verdict"],
        "planted_untested_verdict": planted["verdict"],
        "pass": (
            forced["verdict"] == "UNTESTED"
            and not forced["test_id"]
            and with_id["verdict"] == "AGREE"
            and with_id.get("test_id") == "cmd-echo-readme"
            and planted["verdict"] == "UNTESTED"
            and not planted.get("test_id")
        ),
    }


def three_route() -> dict:
    git_dir = REPO / ".git"
    return {
        "attempted": False,
        "reason": "worktree-is-not-a-git-repository",
        "git_dir_present": git_dir.exists(),
        "recorded_estate_measurement": {
            "source": "command-center/p2-wave/P2-BUILD-ROUND2.md",
            "targets": [
                "command-center/ready_units.py",
                "tools/measure-guard/blobread.py",
            ],
            "result": (
                "git archive+tar returned CRLF; git cat-file -p and git show "
                "returned the LF blob. Only archive converts."
            ),
        },
        "this_linux_worktree": (
            "Cannot re-run the three-route table: this worktree has no .git. "
            "CONTRADICT on the checklist recipe stands on the recorded estate "
            "measurement plus the extracted prescription, not on a fabricated "
            "byte table."
        ),
    }


def mention_control() -> dict:
    from statements import is_archive_lf_blob_prescription

    mention_path = REPO / MENTION_ONLY_FIXTURE
    planted = is_archive_lf_blob_prescription(NEGATED_MENTION)
    live_mention = False
    checklist = REPO / LIVE_CHECKLIST
    if checklist.is_file():
        live_text = checklist.read_text(encoding="utf-8")
        live_mention = "Not `git archive`" in live_text or "Not git archive" in live_text
    return {
        "mention_fixture_present": mention_path.is_file(),
        "negated_mention_is_prescription": planted,
        "live_checklist_documents_the_defect": live_mention,
        "pass": (not planted) and mention_path.is_file(),
    }


def measured() -> dict:
    inventory = live_inventory()
    exec_paths = executable_paths()
    stmt_paths = statement_paths()
    extracted = extract_many(exec_paths, REPO)
    runs = run_all(extracted["commands"], REPO)
    statements: list[dict] = []
    for path in stmt_paths:
        statements.extend(extract_statements(path, REPO))
    classified = join_and_classify(statements, runs)
    silent = validate_no_silent_agree(classified)
    contradict_archive = [
        s
        for s in classified
        if s.get("verdict") == "CONTRADICT"
        and s.get("test_id") == "known-present-git-archive-lf-blob"
    ]
    checklist = REPO / LIVE_CHECKLIST
    snippet_live = False
    snippet_line = None
    if checklist.is_file():
        text = checklist.read_text(encoding="utf-8")
        snippet_live = KNOWN_PRESENT_SNIPPET in text
        if snippet_live:
            snippet_line = text.split(KNOWN_PRESENT_SNIPPET)[0].count("\n") + 1
    planted = REPO / KNOWN_PRESENT_FIXTURE
    snippet_planted = False
    snippet_planted_line = None
    if planted.is_file():
        ptext = planted.read_text(encoding="utf-8")
        snippet_planted = KNOWN_PRESENT_SNIPPET in ptext
        if snippet_planted:
            snippet_planted_line = ptext.split(KNOWN_PRESENT_SNIPPET)[0].count("\n") + 1
    noexec = noexec_both_states()
    untested = untested_control()
    mention = mention_control()
    agree = [s for s in classified if s["verdict"] == "AGREE"]
    untested_rows = [s for s in classified if s["verdict"] == "UNTESTED"]
    contradict = [s for s in classified if s["verdict"] == "CONTRADICT"]
    snippet_present = snippet_live or snippet_planted
    known_present = {
        "id": "known-present-git-archive-lf-blob",
        "snippet": KNOWN_PRESENT_SNIPPET,
        "live_path": LIVE_CHECKLIST,
        "live_present": checklist.is_file(),
        "snippet_in_live_checklist": snippet_live,
        "snippet_line": snippet_line,
        "planted_path": KNOWN_PRESENT_FIXTURE,
        "snippet_in_planted_fixture": snippet_planted,
        "planted_line": snippet_planted_line,
        "extracted_as_statement": any(
            is_archive_lf_blob_prescription(s["text"]) for s in classified
        ),
        "marked_contradict": len(contradict_archive) >= 1,
        "fired": bool(snippet_present and contradict_archive and not silent),
        "rows": [
            {
                "anchor": s["anchor"],
                "verdict": s["verdict"],
                "test_id": s["test_id"],
                "text": s["text"],
            }
            for s in contradict_archive
        ],
    }
    commands_out = []
    for r in runs:
        commands_out.append(
            {
                "id": r["id"],
                "doc_anchor": r["doc_anchor"],
                "path": r["path"],
                "line": r["line"],
                "invocation": r["invocation"],
                "exit_code": r["exit_code"],
                "stdout_head": (r.get("stdout_head") or "")[:200],
                "stderr_head": (r.get("stderr_head") or "")[:200],
                "attempted": r["attempted"],
                "classification": r["classification"],
                "reason": r["reason"],
            }
        )
    fp = {
        "known_present_fired": known_present["fired"],
        "contradict_git_archive_count": len(contradict_archive),
        "noexec_skipped_count": extracted["skipped_count"],
        "noexec_both_states": noexec["pass"],
        "agree_count": len(agree),
        "agree_without_test_id": len(silent),
        "untested_count": len(untested_rows),
        "contradict_count": len(contradict),
        "commands_extracted": extracted["command_count"],
        "commands_attempted": sum(1 for r in runs if r["attempted"]),
        "untested_control": untested["pass"],
        "mention_not_prescription": mention["pass"],
        "docs_scanned": len(extracted["docs"]),
        "statement_docs_scanned": len(stmt_paths),
    }
    return {
        "live_inventory": inventory,
        "docs_scanned": extracted["docs"],
        "statement_docs": [p.relative_to(REPO).as_posix() for p in stmt_paths],
        "commands": commands_out,
        "skipped_noexec": extracted["skipped"],
        "behaviour_statements": classified,
        "known_present_control": known_present,
        "noexec_control": noexec,
        "untested_control": untested,
        "mention_control": mention,
        "three_route": three_route(),
        "fingerprint": fp,
        "probe_commands": {"probe1": P1, "probe2": P2},
        "silent_agree": silent,
    }


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:SYN-0020 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1
