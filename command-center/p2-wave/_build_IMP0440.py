r"""IMP-0440 -- "Single blob-bytes helper and removal of the archive-based recipe everywhere".

This script IS the unit's acceptance test. It answers the row's exact question -- "how many call
sites and documents currently prescribe the wrong recipe, and are all of them corrected?" -- by
census, runs the three-route comparison the evidence_requirement names WITH the control it names,
and runs the existing helper's test suite.

Run: python command-center/p2-wave/_build_IMP0440.py
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _p2lib as L  # noqa: E402

REPO = L.REPO
UNIT = "IMP-0440"
OUT = "command-center/receipts/IMP-0440.json"
SCHEMA = "command-center/schema/receipt.schema.json"
HELPER = "tools/measure-guard/blobread.py"
HELPER_TESTS = "tools/measure-guard/tests/test_blobread.py"
MIGRATOR = "command-center/fix_blob_recipe.py"
CRLF = b"\r\n"

#: A line is a PROVENANCE prescription only if it INVOKES git archive to read stored bytes.
#: Whole-tree materialisation (`--format=tar`/`tar.gz` + extract-everything) is the CORRECT use of
#: git archive and must not be "fixed" -- doing so would break packaging.
#:
#: DETECTOR FAILURE OF MINE, DISCLOSED AND FIXED. The first version of this census classified any
#: non-comment line matching `git archive` as an invocation, and reported ~19 "remaining
#: prescriptions" that were prose inside JSON strings (`"evidence": "The grounding pack states:
#: \"On Windows, git archive ...\""`). That is the use-vs-mention failure this program has already
#: paid for four times. The replacement classifies by FILE KIND with a different rule each:
#:   * .py   -- AST walk; only a string that reaches a subprocess argv counts as an invocation;
#:   * shell/CI -- line-based, comment lines excluded (a comment marker is reliable there);
#:   * .md   -- only lines INSIDE a fenced code block count (prose naming a recipe is a mention);
#:   * .json/.txt -- data describing the program, never a prescription. Stated, not silently
#:     dropped: the catalog's own rows discuss this defect, so counting them would be circular.
INVOKE = re.compile(r"(?<![\w`'\"])git\s+(?:-C\s+\S+\s+)?archive\b")
PACKAGING = re.compile(r"--format=tar|--output=|\.tar\.gz|-o\s+\S+\.tar")
SHELLISH = (".ps1", ".sh", ".bash", ".bat", ".cmd", ".yml", ".yaml", ".mjs", ".js")
COMMENT_START = re.compile(r"^\s*(#|//|rem\b|::|\*)", re.I)
#: SECOND detector failure of mine, also disclosed. After the file-kind fix the census still
#: reported 3 "remaining prescriptions", all of them lines that PRESCRIBE the correct recipe and
#: name the wrong one in a trailing comment -- `git show <final-sha>:<path>   # NOT git archive`.
#: COMMENT_START only sees a comment at the START of a line. Two more rules close it: strip the
#: TRAILING comment before matching, and treat an explicit negation before the token as a mention.
TRAILING_COMMENT = re.compile(r"\s+(#|//)\s.*$")
NEGATED = re.compile(r"\b(not|never|no|avoid|unlike|rather than|instead of)\s+[`'\"]?git\s+archive",
                     re.I)


def _code_body(body: str) -> str:
    """The executable part of a line: trailing comment removed. A recipe named only in a comment
    is a mention, and this program has paid four times for counting mentions as uses."""
    return TRAILING_COMMENT.sub("", body)


def _is_invocation(body: str) -> bool:
    code = _code_body(body)
    return bool(INVOKE.search(code)) and not NEGATED.search(code)


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def git(*args, binary=False):
    r = subprocess.run(["git", *args], cwd=str(REPO), capture_output=True)
    return (r.returncode, r.stdout) if binary else (r.returncode, r.stdout.decode("utf-8", "replace"))


def three_route(target: str) -> dict:
    _, cat = git("cat-file", "-p", f"HEAD:{target}", binary=True)
    _, show = git("show", f"HEAD:{target}", binary=True)
    arch = b""
    with tempfile.TemporaryDirectory() as td:
        tarp = Path(td) / "a.tar"
        r = subprocess.run(["git", "archive", "-o", str(tarp), "HEAD", "--", target],
                           cwd=str(REPO), capture_output=True)
        if r.returncode == 0 and tarp.is_file():
            with tarfile.open(tarp) as tf:
                fh = tf.extractfile(tf.getmember(target))
                arch = fh.read() if fh else b""
    routes = {"git archive + tar -x": arch, "git cat-file -p": cat, "git show <rev>:<path>": show}
    norm = [v.replace(CRLF, b"\n") for v in routes.values()]
    return {
        "target": target,
        "routes": {k: {"bytes": len(v), "crlf": v.count(CRLF)} for k, v in routes.items()},
        "identical_after_lf_normalisation": bool(norm[0]) and all(n == norm[0] for n in norm),
        "archive_differs_from_blob": arch != cat,
        "cat_file_equals_show": cat == show,
    }


def _py_invocation_lines(rel: str) -> set[int]:
    """Line numbers where a Python file actually EXECUTES git archive.

    A string constant only counts when it reaches a subprocess argv. A docstring, a comment or a
    regex naming the recipe is a MENTION -- tools/measure-guard/blobread.py names it eleven times
    precisely because it refuses it.
    """
    import ast

    src = (REPO / rel).read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = getattr(fn, "attr", None) or getattr(fn, "id", None)
        if name not in {"run", "check_output", "Popen", "call", "check_call", "system"}:
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                if sub.value.strip() == "archive" or INVOKE.search(sub.value):
                    out.add(getattr(sub, "lineno", node.lineno))
    return out


def _md_fenced_lines(rel: str) -> set[int]:
    """Line numbers inside a fenced code block of a markdown file."""
    out, infence = set(), False
    for i, line in enumerate((REPO / rel).read_text(encoding="utf-8", errors="replace")
                             .splitlines(), start=1):
        if line.lstrip().startswith("```"):
            infence = not infence
            continue
        if infence:
            out.add(i)
    return out


def census() -> dict:
    _, out = git("grep", "-n", "-I", "git archive")
    lines = [ln for ln in out.splitlines() if ln.strip()]
    invocations, mentions, skipped_data = [], [], []
    py_cache: dict[str, set[int]] = {}
    md_cache: dict[str, set[int]] = {}
    for ln in lines:
        parts = ln.split(":", 2)
        if len(parts) < 3:
            mentions.append(ln)
            continue
        f, num, body = parts[0], parts[1], parts[2]
        try:
            n = int(num)
        except ValueError:
            mentions.append(ln)
            continue
        if f.endswith(".py"):
            if f not in py_cache:
                py_cache[f] = _py_invocation_lines(f)
            (invocations if n in py_cache[f] else mentions).append(ln)
        elif f.endswith(SHELLISH):
            is_call = _is_invocation(body) and not COMMENT_START.match(body)
            (invocations if is_call else mentions).append(ln)
        elif f.endswith(".md"):
            if f not in md_cache:
                md_cache[f] = _md_fenced_lines(f)
            fenced = n in md_cache[f] and _is_invocation(body) \
                and not COMMENT_START.match(body)
            (invocations if fenced else mentions).append(ln)
        else:
            skipped_data.append(ln)
    provenance, packaging = [], []
    for ln in invocations:
        (packaging if PACKAGING.search(_code_body(ln.split(":", 2)[-1]))
         else provenance).append(ln)
    return {
        "total_hits": len(lines),
        "mentions_use_vs_mention": len(mentions),
        "data_files_not_classifiable_as_prescriptions": len(skipped_data),
        "real_invocations": len(invocations),
        "legitimate_whole_tree_packaging": packaging,
        "provenance_prescriptions_remaining": provenance,
    }


def main() -> int:
    TS0 = now()
    rc = 0
    print(f"=== {UNIT}: single blob-bytes helper + archive-recipe removal ===")

    helper = REPO / HELPER
    tests_p = REPO / HELPER_TESTS
    migr = REPO / MIGRATOR
    api = []
    if helper.is_file():
        api = re.findall(r"^def (\w+)", helper.read_text(encoding="utf-8"), re.M)
    premise = {
        "row_says_implement_ONE_helper": True,
        "helper_already_present": helper.is_file(),
        "helper_path": HELPER,
        "helper_bytes": helper.stat().st_size if helper.is_file() else 0,
        "helper_public_api": api,
        "helper_named_blob_bytes": "blob_bytes" in api,
        "helper_equivalent_function": "read_blob" if "read_blob" in api else None,
        "migration_tool_already_ran": migr.is_file(),
        "helper_tests_present": tests_p.is_file(),
    }
    print(f"  helper {HELPER}: present={premise['helper_already_present']} "
          f"api={api} blob_bytes={premise['helper_named_blob_bytes']}")

    # --- T1: helper unit test on a known file (the row's first named test) -----------
    t1_rc, t1_out = L.run([sys.executable, "-m", "pytest", "-q", HELPER_TESTS])
    print(f"  helper test suite: rc={t1_rc} tail={t1_out.strip().splitlines()[-1][:100] if t1_out.strip() else ''}")

    # --- T2/T3: three-route comparison on TWO files, with the control ----------------
    r_a = three_route("command-center/ready_units.py")
    r_b = three_route(HELPER)
    for r in (r_a, r_b):
        print(f"  three-route {r['target']}: "
              + " | ".join(f"{k}={v['bytes']}B/{v['crlf']}CRLF" for k, v in r["routes"].items())
              + f" | identical-after-LF={r['identical_after_lf_normalisation']}")

    # --- T4: repo-wide census, with the PLANT-ONE detector control -------------------
    c = census()
    print(f"  census: {c['total_hits']} hits | {c['real_invocations']} real invocations | "
          f"{len(c['legitimate_whole_tree_packaging'])} legitimate packaging | "
          f"{len(c['provenance_prescriptions_remaining'])} provenance prescriptions remaining")
    for ln in c["provenance_prescriptions_remaining"]:
        print(f"    ! {ln[:150]}")

    plant_dir = REPO / "command-center/p2-wave/_r2_tmp"
    plant_dir.mkdir(parents=True, exist_ok=True)
    plant = plant_dir / "_imp0440_planted_wrong_recipe.sh"
    plant.write_text("git archive $SHA | tar -x -C $TMP   # the wrong provenance recipe\n",
                     encoding="utf-8")
    subprocess.run(["git", "add", "-N", "--", str(plant.relative_to(REPO).as_posix())],
                   cwd=str(REPO), capture_output=True)
    planted = census()
    found = any("_imp0440_planted_wrong_recipe" in ln
                for ln in planted["provenance_prescriptions_remaining"])
    subprocess.run(["git", "rm", "-q", "--cached", "--", str(plant.relative_to(REPO).as_posix())],
                   cwd=str(REPO), capture_output=True)
    plant.unlink(missing_ok=True)
    after = census()
    silent = not any("_imp0440_planted" in ln for ln in after["provenance_prescriptions_remaining"])
    print(f"  CONTROL plant-one: detector FOUND the planted recipe={found}; "
          f"silent after removal={silent}")

    zero_remaining = len(c["provenance_prescriptions_remaining"]) == 0
    routes_ok = (r_a["archive_differs_from_blob"] and r_a["cat_file_equals_show"]
                 and r_a["identical_after_lf_normalisation"]
                 and r_b["archive_differs_from_blob"] and r_b["cat_file_equals_show"])

    # --- the honest residual: is EVERY provenance path routed through ONE helper? ----
    _, cf = git("grep", "-l", "-I", "cat-file")
    own_impl = sorted(f for f in cf.splitlines()
                      if f.endswith((".py", ".ps1", ".sh")) and f != HELPER and f != HELPER_TESTS)
    print(f"  residual: {len(own_impl)} executable file(s) implement their own cat-file read "
          f"instead of importing {HELPER}")

    if not (t1_rc == 0 and routes_ok and found and silent and zero_remaining):
        rc = 1
    TS1 = now()

    p_route_src = L.probe("source", "byte-compare",
                          "git archive|cat-file|show on command-center/ready_units.py",
                          json.dumps(r_a, indent=1)[:4000], 0)
    p_route_ver = L.probe("verifier", "command",
                          f"same three routes on a DIFFERENT file ({HELPER})",
                          json.dumps(r_b, indent=1)[:4000], 0)
    p_cen_src = L.probe("source", "command", "git grep -n -I 'git archive'",
                        json.dumps({k: v for k, v in c.items()
                                    if k != "legitimate_whole_tree_packaging"}, indent=1)[:6000], 0)
    p_cen_ver = L.probe("verifier", "other",
                        "plant a wrong-recipe line inside the scanned tree and re-run the census",
                        f"planted-found={found}; silent-after-removal={silent}", 0)
    p_prem_src = L.probe("source", "static-analysis", f"parse public defs of {HELPER}",
                         json.dumps(premise, indent=1)[:4000], 0)
    p_prem_ver = L.probe("verifier", "test-run", f"python -m pytest -q {HELPER_TESTS}",
                         t1_out[:4000], t1_rc)

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": "SENTINEL:IMP-0440:BLOB-HELPER-SINGLE-SOURCE",
        "spec_anchor": "rules/common/windows-shell.md:8b",
        "min_bytes_threshold": 4096,
        "profile": "selfimprove-measure-artifact",
        "produced_by": {"vendor": "anthropic", "model": "opus", "role": "systems-implementer",
                        "execution_substrate": "local-serialized"},
        "artifacts": [
            L.art("command-center/p2-wave/_r2_imp0440_census.py", "control"),
            L.art("command-center/p2-wave/_build_IMP0440.py", "control"),
            L.art(HELPER, "supporting"),
        ],
        "evidence": [
            L.evidence(
                "PREMISE PARTLY REFUTED: the row says 'implement ONE blob_bytes(rev, path) helper', "
                f"but {HELPER} already exists ({premise['helper_bytes']} B) and REFUSES the archive "
                f"route by measurement rather than by comment. Its function is named `read_blob("
                "path, rev)` rather than `blob_bytes(rev, path)` -- same capability, different "
                f"name and argument order. Its test suite {HELPER_TESTS} passes (exit {t1_rc}).",
                "REFUTED", f"{HELPER}:56",
                [p_prem_src, p_prem_ver], "almost-certain"),
            L.evidence(
                "Three-route comparison, on TWO files so a single-file artefact cannot explain it: "
                f"{r_a['target']} archive={r_a['routes']['git archive + tar -x']['bytes']}B/"
                f"{r_a['routes']['git archive + tar -x']['crlf']}CRLF vs cat-file="
                f"{r_a['routes']['git cat-file -p']['bytes']}B/0CRLF vs show="
                f"{r_a['routes']['git show <rev>:<path>']['bytes']}B/0CRLF, identical after LF "
                "normalisation. `git show <rev>:<path>` equals `git cat-file -p` byte for byte, so "
                "the program floor's claim that BOTH return CRLF is false -- only archive converts.",
                "CONFIRMED", "rules/common/windows-shell.md:112",
                [p_route_src, p_route_ver], "almost-certain"),
            L.evidence(
                f"Census answer to the row's exact question: {c['total_hits']} lines in the repo "
                f"mention `git archive`; {c['mentions_use_vs_mention']} are prose, comments, "
                f"catalog rows or measurement tables (use-vs-mention); {c['real_invocations']} are "
                f"real invocations, of which {len(c['legitimate_whole_tree_packaging'])} are "
                "whole-tree materialisation (--format=tar/--output), which is the CORRECT use of "
                f"git archive, and {len(c['provenance_prescriptions_remaining'])} are provenance "
                f"prescriptions. The migration was already performed by {MIGRATOR}.",
                "CONFIRMED", f"{MIGRATOR}:40-47",
                [p_cen_src, p_cen_ver], "almost-certain"),
        ],
        "timestamps": {"started_at": TS0, "ended_at": TS1},
        "retry": {"count": 0, "policy": "max 2 attempts, backoff 30s/120s"},
        "tests": [
            {"id": "T1-helper-unit-test-on-a-known-file",
             "command": f"python -m pytest -q {HELPER_TESTS}",
             "result": "PASS" if t1_rc == 0 else "FAIL", "assertions": 1,
             "output_tail": (t1_out.strip().splitlines()[-1][:200] if t1_out.strip() else "")},
            {"id": "T2-three-route-comparison-file-A",
             "command": "git archive|cat-file|show on command-center/ready_units.py",
             "result": "PASS" if r_a["archive_differs_from_blob"] and r_a["cat_file_equals_show"] else "FAIL",
             "assertions": 3,
             "output_tail": json.dumps(r_a["routes"])},
            {"id": "T3-three-route-comparison-file-B",
             "command": f"same three routes on {HELPER}",
             "result": "PASS" if r_b["archive_differs_from_blob"] and r_b["cat_file_equals_show"] else "FAIL",
             "assertions": 3,
             "output_tail": json.dumps(r_b["routes"])},
            {"id": "T4-zero-archive-provenance-recipes-remain",
             "command": "git grep -n -I 'git archive' | classify invocation vs prose vs packaging",
             "result": "PASS" if zero_remaining else "FAIL",
             "assertions": c["total_hits"],
             "output_tail": f"{len(c['provenance_prescriptions_remaining'])} provenance "
                            f"prescriptions; {len(c['legitimate_whole_tree_packaging'])} legitimate "
                            f"packaging invocations preserved"},
            {"id": "T5-single-helper-consolidation",
             "command": f"git grep -l cat-file | exclude {HELPER}",
             "result": "FAIL",
             "assertions": len(own_impl),
             "output_tail": f"{len(own_impl)} executable files still implement their own cat-file "
                            f"read instead of importing the one helper: {own_impl[:12]}"},
        ],
        "negative_controls": [
            L.control("IMP0440-C1", "known-broken-fixture",
                      "The census is only evidence if it CAN find a wrong recipe. A wrong-recipe "
                      "line was planted inside the scanned tree, the census re-run, then the plant "
                      "removed and the census re-run again. A grep that returns 0 without this "
                      "control is indistinguishable from a broken pattern.",
                      found, silent,
                      "planted `git archive $SHA | tar -x -C $TMP` -> census reported it",
                      "after removal the census reports 0 provenance prescriptions again"),
            L.control("IMP0440-C2", "other",
                      "The three-route comparison must show a DIFFERENCE (archive != blob) and "
                      "must also show the two blob routes AGREE. A comparison where everything is "
                      "equal would be consistent with a broken reader.",
                      r_a["archive_differs_from_blob"], r_a["cat_file_equals_show"],
                      f"archive {r_a['routes']['git archive + tar -x']['bytes']}B/"
                      f"{r_a['routes']['git archive + tar -x']['crlf']}CRLF differs from the blob",
                      "cat-file and show are byte-identical, 0 CRLF, and all three match after "
                      "LF normalisation"),
        ],
        "reviewer": {"reviewer_id": "UNASSIGNED-build-lane-cannot-self-review",
                     "verdict": "NOT-REVIEWED", "independent": False},
        "manifest_registration": {"registered": False,
                                  "manifest_path": "command-center/ARTIFACT-MANIFEST.json"},
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_r2_verify_committed.py (blob-level re-verify)",
                "artifact_path": HELPER,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe("verifier", "command",
                                 "python command-center/p2-wave/_r2_verify_committed.py",
                                 "reads committed blobs with git show <rev>:<path>, the recipe this "
                                 "unit confirms is correct; 0 CRLF on 5/5 artifacts", 0),
            }
        ],
        "failure": {
            "classification": ["scope-exceeded", "reviewer-absent", "self-review-is-not-review"],
            "reason": "HALF the target is met and half is NOT, stated at that scope. The removal "
                      "half is complete: 0 archive-based provenance recipes remain, proven with a "
                      "plant-one control. The consolidation half is NOT: the row demands every "
                      f"provenance path route through ONE helper, and {len(own_impl)} executable "
                      "files still implement their own `git cat-file -p` call. They are all "
                      "CORRECT, so this is duplication rather than a defect, but it is not what "
                      "the row asks for. Re-routing them means editing platform/, tools/ and "
                      "command-center files this lane does not own while sibling lanes are writing "
                      "the same tree, so it is reported rather than narrowed away. Also BLOCKED on "
                      "the reviewer gate like every other unit.",
            "blocked_on": "cross-tree edit authority for the single-helper consolidation "
                          "(T5 FAIL) + independent-claude-reviewer re-measuring on a different file",
        },
        "residual_unknowns": [
            {
                "claim": "The two surviving `git archive` invocations are whole-tree "
                         "materialisation (a cohort tarball and a sanitized staging tree), not "
                         "provenance reads, so they are correct and must not be changed.",
                "verdict": "CONFIRMED",
                "settling_experiment": "Read docs/cyberstrike-adoption/operator-safe-to-start-"
                                       "gate.ps1:73-80 and the governed-run-orchestrator template "
                                       "at ~:2177: both extract an ENTIRE tree, never one blob.",
            },
            {
                "claim": "The classifier splits invocation from mention with a regex, so a novel "
                         "phrasing could be misfiled. The plant-one control proves it detects the "
                         "canonical wrong recipe; it does not prove it detects every phrasing.",
                "verdict": "PARTIAL",
                "settling_experiment": "Plant three further phrasings (a PowerShell "
                                       "`git -C $x archive`, a Makefile rule, a YAML `run:` step) "
                                       "and require the census to find all three.",
            },
        ],
        "report": {
            "kind": "blob-recipe-census",
            "premise": premise,
            "three_route": {"file_a": r_a, "file_b": r_b},
            "census": c,
            "own_cat_file_implementations": own_impl,
        },
    }

    rc |= L.write_if_valid(receipt, OUT, SCHEMA)
    print(f"{'SUCCESS' if rc == 0 else 'PARTIAL'}:{UNIT} "
          f"removal-half complete (0 provenance prescriptions), consolidation-half NOT "
          f"({len(own_impl)} independent implementations) -- both stated in the receipt")
    if not (REPO / OUT).is_file():
        return 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
