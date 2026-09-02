"""Build the SYN-0005 decision trace from live catalog + disk hops."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import namespaces as NS

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
SELF_ID = "SYN-0005"
DECLARED_INPUTS = (
    ("command-center/OWNER-DECISIONS.md", "owner-decisions"),
    ("command-center/OPTION-ID-RESOLUTION.json", "option-namespace-registry"),
    ("command-center/WORK-UNIT-CATALOG.json", "catalog"),
    ("command-center/ARTIFACT-MANIFEST.json", "artifact-manifest"),
    ("command-center/TEST-REGISTRY.json", "test-registry"),
    ("command-center/events/EVENTS.jsonl", "events"),
    (
        "command-center/synthesis/SYN-0001.root-cause-hierarchy.json",
        "dependency-SYN-0001",
    ),
)
OPTION_UNIVERSE = "07-OPTION-UNIVERSE.json"
BT_RE = re.compile(r"`([^`]{4,120})`")
UNIT_IN_TEXT = re.compile(r"\b(?:[A-Z]{2,5}-\d{4}|R-[A-Z]\d{2})\b")
SKIP_OPTION_NS = frozenset({"owner-question", "work-unit-or-register-item"})


def lf_read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def present(repo: Path, rel: str, absent: set[str]) -> bool:
    norm = rel.replace("\\", "/")
    if norm in absent:
        return False
    fp = repo / norm
    try:
        return fp.is_file() and fp.stat().st_size > 0
    except OSError:
        return False


def load_json(path: Path):
    return json.loads(lf_read(path))


def id_line_map(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    rx = re.compile(r'"id":\s*"([^"]+)"')
    for i, line in enumerate(text.splitlines(), 1):
        m = rx.search(line)
        if m and m.group(1) not in out:
            out[m.group(1)] = i
    return out


def boundary_hit(blob: str, needle: str) -> bool:
    if not needle or len(needle) < 2:
        return False
    if "/" in needle or needle.endswith(".md") or needle.endswith(".json"):
        return needle in blob
    pat = r"(?<![A-Za-z0-9_])" + re.escape(needle) + r"(?![A-Za-z0-9_])"
    return re.search(pat, blob) is not None


def any_hit(blob: str, needles: list[str]) -> bool:
    return any(boundary_hit(blob, n) for n in needles)


def decision_needles(q: dict, resolved_opts: list[str]) -> list[str]:
    qid = str(q.get("id") or "")
    # Bare Q<n> collides with Phase-13 matrix ids (Q01..Q11) on BLD receipts.
    # Join those owner questions via owner_gate, option tokens, and paths.
    needles: list[str] = []
    if qid and not re.fullmatch(r"Q\d+", qid):
        needles.append(qid)
    needles.extend(resolved_opts)
    blob = " ".join(
        [
            str(q.get("text") or ""),
            str(q.get("answer") or ""),
            str(q.get("answer_detail") or ""),
        ]
    )
    for tok in UNIT_IN_TEXT.findall(blob):
        if tok != SELF_ID:
            needles.append(tok)
    for tok in re.findall(r"\b[A-Z]{2,}(?:-[A-Z0-9]+){1,3}\b", blob):
        if tok != qid and tok not in {"JSON", "TODO"}:
            needles.append(tok)
    generic_bt = {
        "hooks",
        "hooks/",
        "skills",
        "skills/",
        "rules",
        "rules/",
        "docs",
        "src",
        "tests",
    }
    for bt in BT_RE.findall(blob):
        cleaned = bt.replace("\\", "/").strip()
        if cleaned.lower() in generic_bt or len(cleaned) < 8:
            continue
        needles.append(bt)
        base = cleaned.split("/")[-1]
        if (
            base
            and base.lower() not in generic_bt
            and ("." in base or len(base) >= 12)
            and base not in needles
        ):
            needles.append(base)
    # Dedup, drop the decision's own option-like self-match handled separately.
    out: list[str] = []
    seen: set[str] = set()
    for n in needles:
        n = n.strip()
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def unit_record(kind: str, rec: dict) -> dict:
    tests = rec.get("tests_required") or []
    if not isinstance(tests, list):
        tests = []
    return {
        "id": str(rec.get("id") or ""),
        "kind": kind,
        "output_path": str(rec.get("output_path") or "").replace("\\", "/"),
        "title": str(rec.get("title") or rec.get("target") or ""),
        "tests_required": [str(t) for t in tests],
        "blob": json.dumps(rec, ensure_ascii=False),
    }


def last_test_result(repo: Path, uid: str) -> str:
    ret_path = (
        repo
        / "command-center"
        / "p2-wave"
        / "probes"
        / uid
        / "SUBAGENT-RETURN.json"
    )
    if not ret_path.is_file():
        return "NOT-RUN"
    try:
        ret = load_json(ret_path)
    except (OSError, json.JSONDecodeError):
        return "NOT-RUN"
    if not isinstance(ret, dict):
        return "NOT-RUN"
    st = str(ret.get("status") or ret.get("state") or "").upper()
    line = str(ret.get("measure_line") or "")
    meas = ret.get("measure") if isinstance(ret.get("measure"), dict) else {}
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return "FAIL"
    if meas.get("exit_code") == 0 or line.startswith("SUCCESS:"):
        return "PASS"
    if st in {"DELIVERED", "SUCCESS"}:
        return "PASS"
    return "NOT-RUN"


def outcome_for(q: dict, hops: dict[str, str], tests: list[dict]) -> str:
    state = str(q.get("state") or "").upper()
    answer = str(q.get("answer") or "")
    if state == "ANSWERED" and answer.upper().startswith("NO"):
        return "REJECTED-WITH-OWNER-REASONING"
    if hops.get("option") == "BROKEN" or hops.get("unit") == "BROKEN":
        return "BROKEN-CHAIN" if state == "ANSWERED" else "DEFERRED"
    if hops.get("artifact") == "BROKEN":
        return "BROKEN-CHAIN" if state == "ANSWERED" else "OPEN"
    if hops.get("test") == "BROKEN":
        if state == "ANSWERED" and hops.get("unit") == "OK" and hops.get("artifact") == "OK":
            return "NO-COVERAGE"
        return "BROKEN-CHAIN" if state == "ANSWERED" else "OPEN"
    if state == "OPEN":
        return "OPEN" if hops.get("unit") == "OK" else "DEFERRED"
    if hops.get("unit") == "OK" and hops.get("artifact") == "OK" and hops.get("test") == "OK":
        return "IMPLEMENTED"
    if hops.get("unit") == "OK":
        return "BROKEN-CHAIN"
    return "NO-COVERAGE"


def build(repo: Path, absent_paths: set[str] | None = None) -> dict:
    absent = {p.replace("\\", "/") for p in (absent_paths or set())}
    cat_path = repo / CATALOG_REL
    cat_text = lf_read(cat_path)
    catalog = json.loads(cat_text)
    lines = id_line_map(cat_text)
    questions = list(catalog.get("owner_questions") or [])
    items = [unit_record("register-item", it) for it in (catalog.get("items") or [])]
    work = [unit_record("work-unit", u) for u in (catalog.get("work_units") or [])]
    universe = [u for u in items + work if u["id"] and u["id"] != SELF_ID]

    gated: dict[str, list[str]] = defaultdict(list)
    for it in catalog.get("items") or []:
        if not isinstance(it, dict):
            continue
        uid = str(it.get("id") or "")
        for g in it.get("owner_gate") or []:
            gated[str(g)].append(uid)

    by_uid = {u["id"]: u for u in universe}
    artifact_text: dict[str, str] = {}
    for u in universe:
        rel = u["output_path"]
        if rel and present(repo, rel, set()):
            fp = repo / rel
            try:
                if fp.stat().st_size <= 2_000_000:
                    artifact_text[rel] = lf_read(fp)
            except (OSError, UnicodeDecodeError):
                artifact_text[rel] = ""

    inventory = []
    for rel, role in DECLARED_INPUTS:
        inventory.append(
            {
                "path": rel,
                "present": present(repo, rel, set()),
                "role": role,
            }
        )
    inventory.append(
        {
            "path": OPTION_UNIVERSE,
            "present": present(repo, OPTION_UNIVERSE, set()),
            "role": "option-universe-70",
        }
    )

    decisions = []
    breaks: list[dict] = []
    reverse: list[dict] = []
    covered_paths: set[str] = set()

    for q in questions:
        qid = str(q.get("id") or "")
        text = str(q.get("text") or "")
        answer = str(q.get("answer") or "")
        detail = str(q.get("answer_detail") or "")
        blob = f"{text}\n{answer}\n{detail}"
        line = lines.get(qid, 0)
        anchor = f"{CATALOG_REL}:{line}" if line else CATALOG_REL
        tokens = NS.extract_tokens(blob)
        resolved_rows = []
        resolved_opt_ids = []
        option_broken = False
        for tok in tokens:
            if tok == qid:
                continue
            row = NS.resolve(tok)
            if row.get("kind") == "option-id" or row.get("status") == "REJECTED":
                resolved_rows.append(row)
            if row.get("kind") == "option-id" and row.get("status") == "RESOLVED":
                resolved_opt_ids.append(tok)
            if row.get("status") == "REJECTED":
                option_broken = True
                breaks.append(
                    {
                        "decision_id": qid,
                        "hop": "option",
                        "classification": "ambiguous-option-token",
                        "token": tok,
                        "detail": row.get("reason") or "bare option token rejected",
                    }
                )
            elif row.get("kind") == "option-id" and row.get("status") == "UNRESOLVED":
                option_broken = True
                breaks.append(
                    {
                        "decision_id": qid,
                        "hop": "option",
                        "classification": "broken-trace-hop",
                        "token": tok,
                        "detail": f"option token {tok} did not resolve to one namespace",
                    }
                )

        if qid == "OQ-1" and not present(repo, OPTION_UNIVERSE, set()):
            option_broken = True
            breaks.append(
                {
                    "decision_id": qid,
                    "hop": "option",
                    "classification": "incomplete-option-set",
                    "detail": (
                        "OQ-1 accepts 70 owner_decisions from 07-OPTION-UNIVERSE.json "
                        "but that file is absent; only tokens named in the answer were resolved"
                    ),
                }
            )

        needles = decision_needles(q, resolved_opt_ids)
        unit_ids: list[str] = []
        seen_u: set[str] = set()
        for uid in gated.get(qid, []):
            if uid not in seen_u and uid in by_uid:
                seen_u.add(uid)
                unit_ids.append(uid)
        for u in universe:
            if u["id"] in seen_u:
                continue
            hay = u["blob"]
            rel = u["output_path"]
            if rel in artifact_text:
                hay = hay + "\n" + artifact_text[rel]
            if any_hit(hay, needles):
                seen_u.add(u["id"])
                unit_ids.append(u["id"])

        artifacts = []
        missing_art = []
        present_art = []
        for uid in unit_ids:
            rel = by_uid[uid]["output_path"]
            if not rel:
                continue
            ok = present(repo, rel, absent)
            row = {
                "path": rel,
                "present": ok,
                "unit_id": uid,
                "bytes": (repo / rel).stat().st_size
                if ok and (repo / rel).is_file()
                else 0,
            }
            artifacts.append(row)
            if ok:
                present_art.append(rel)
                covered_paths.add(rel)
                reverse.append(
                    {
                        "path": rel,
                        "unit_id": uid,
                        "decision_id": qid,
                        "source_anchor": anchor,
                    }
                )
            else:
                missing_art.append(rel)

        tests = []
        for uid in unit_ids:
            result = last_test_result(repo, uid)
            named = by_uid[uid]["tests_required"]
            if not named:
                tests.append(
                    {
                        "id": f"{uid}:unnamed",
                        "unit_id": uid,
                        "name": "(no tests_required on catalog record)",
                        "result": result if result != "NOT-RUN" else "NOT-RUN",
                    }
                )
            else:
                for i, name in enumerate(named):
                    tests.append(
                        {
                            "id": f"{uid}:t{i}",
                            "unit_id": uid,
                            "name": name,
                            "result": result,
                        }
                    )

        present_units = [a["unit_id"] for a in artifacts if a.get("present")]
        named_on_present = [
            t
            for t in tests
            if t.get("unit_id") in present_units
            and t.get("name") != "(no tests_required on catalog record)"
        ]
        passing_on_present = [
            t for t in named_on_present if t.get("result") == "PASS"
        ]

        hops = {
            "source": "OK",
            "option": "BROKEN" if option_broken else ("OK" if resolved_opt_ids else "EMPTY"),
            "unit": "OK" if unit_ids else "BROKEN",
            "artifact": (
                "BROKEN"
                if (unit_ids and (not present_art or missing_art))
                else ("OK" if present_art else "EMPTY")
            ),
            "test": (
                "EMPTY"
                if not present_units
                else (
                    "BROKEN"
                    if (not named_on_present or not passing_on_present)
                    else "OK"
                )
            ),
        }

        if hops["source"] == "OK" and not present(repo, "command-center/OWNER-DECISIONS.md", set()):
            # Catalog is the live source of truth; declared markdown view is absent.
            breaks.append(
                {
                    "decision_id": qid,
                    "hop": "source",
                    "classification": "declared-input-absent",
                    "detail": (
                        "command-center/OWNER-DECISIONS.md is absent; "
                        "row taken from WORK-UNIT-CATALOG.json owner_questions"
                    ),
                }
            )
            hops["source"] = "BROKEN"

        if hops["unit"] == "BROKEN":
            breaks.append(
                {
                    "decision_id": qid,
                    "hop": "unit",
                    "classification": "broken-trace-hop",
                    "detail": f"no implementing unit joined for {qid}",
                }
            )
        if hops["artifact"] == "BROKEN":
            if missing_art:
                breaks.append(
                    {
                        "decision_id": qid,
                        "hop": "artifact",
                        "classification": "broken-trace-hop",
                        "paths": missing_art[:24],
                        "detail": (
                            f"{len(missing_art)} of {len(artifacts)} unit output_path "
                            f"values missing on disk for {qid}"
                        ),
                    }
                )
            elif not present_art:
                breaks.append(
                    {
                        "decision_id": qid,
                        "hop": "artifact",
                        "classification": "broken-trace-hop",
                        "detail": f"units exist for {qid} but none have a present artifact",
                    }
                )
        if hops["test"] == "BROKEN":
            cls = (
                "decision-with-no-coverage"
                if not named_on_present
                else "broken-trace-hop"
            )
            breaks.append(
                {
                    "decision_id": qid,
                    "hop": "test",
                    "classification": cls,
                    "detail": (
                        f"{qid} present-artifact units={len(present_units)} "
                        f"named_tests={len(named_on_present)} "
                        f"pass={len(passing_on_present)}"
                    ),
                }
            )

        hop_rows = [{"id": k, "status": v} for k, v in hops.items()]
        out_label = outcome_for(q, hops, tests)
        decisions.append(
            {
                "id": qid,
                "decision_state": str(q.get("state") or "").upper(),
                "source_anchor": anchor,
                "decision_text": text,
                "answer": answer or None,
                "answered_on": q.get("answered_on"),
                "answer_provenance": q.get("answer_provenance"),
                "resolved_option_ids": [
                    r
                    for r in resolved_rows
                    if r.get("status") == "RESOLVED"
                ],
                "option_resolutions": resolved_rows,
                "unit_ids": unit_ids,
                "artifacts": artifacts,
                "tests": tests,
                "outcome": out_label,
                "hops": hop_rows,
            }
        )

    for rel, role in DECLARED_INPUTS:
        if not present(repo, rel, set()) and rel != CATALOG_REL:
            breaks.append(
                {
                    "decision_id": None,
                    "hop": "declared-input",
                    "classification": "declared-input-absent",
                    "path": rel,
                    "detail": f"declared input {rel} is absent on this worktree",
                }
            )

    orphans = []
    for u in universe:
        rel = u["output_path"]
        if rel and present(repo, rel, absent) and rel not in covered_paths:
            orphans.append(
                {
                    "path": rel,
                    "unit_id": u["id"],
                    "kind": u["kind"],
                }
            )
            breaks.append(
                {
                    "decision_id": None,
                    "hop": "artifact",
                    "classification": "orphan-artifact",
                    "path": rel,
                    "unit_id": u["id"],
                    "detail": f"{rel} exists on disk but no owner-decision chain reaches it",
                }
            )

    hop_ids = ("source", "option", "unit", "artifact", "test")
    broken_at: dict[str, set[str]] = {h: set() for h in hop_ids}
    for b in breaks:
        hid = str(b.get("hop") or "")
        did = b.get("decision_id")
        if hid in broken_at and isinstance(did, str) and did:
            broken_at[hid].add(did)
    hop_break_counts = {h: len(broken_at[h]) for h in hop_ids}

    return {
        "unit_id": SELF_ID,
        "report_kind": "decision-trace",
        "decisions": decisions,
        "breaks": breaks,
        "hop_break_counts": hop_break_counts,
        "reverse_index": reverse,
        "input_inventory": inventory,
        "orphans": orphans,
        "derivation": (
            "owner_questions in WORK-UNIT-CATALOG.json (OWNER-DECISIONS.md is "
            "the derived render and is absent); option tokens resolved by "
            "command-center/p2-wave/probes/SYN-0005/namespaces.py; units joined "
            "by owner_gate, id/option/path needles, and present output_path bytes"
        ),
    }


def decisions_by_id(doc: dict) -> dict[str, dict]:
    return {str(d["id"]): d for d in doc.get("decisions") or []}
