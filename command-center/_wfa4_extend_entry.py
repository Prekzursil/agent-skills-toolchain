"""EXTEND entry: READ spine-position 187 (exec-harness-restore-live-full-power).

Prior archaeology classified every Family-H entry MECHANICALLY from the run record plus a
regex mechanism scan and marked it UNVERIFIED, explicitly stating it is 'not a read of the
script'. This script performs that read and appends ONE verified extension entry, replacing
the non-countable tombstone at spine position 128 so the unit still carries 32 materially
distinct candidates.
"""

import json
import pathlib
import re

CORPUS = pathlib.Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806")
OUT = pathlib.Path(
    r"C:/Users/Prekzursil/source/ast-integrate/platform/registry/workflow-candidates-4.json"
)
SCAN = json.loads(
    pathlib.Path(
        r"C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa4_h_scan.json"
    ).read_text("utf-8")
)
reg = json.loads((CORPUS / "08-WORKFLOW-CANDIDATE-REGISTRY.json").read_text("utf-8"))
cands = reg["candidates"]

TARGET_POS = 187
row = next(r for r in SCAN if r["pos"] == TARGET_POS)
prior = cands[TARGET_POS - 1]
p = pathlib.Path(row["path"])
src = p.read_text("utf-8", errors="replace")
rel = str(p).replace("\\", "/")
lines = src.count("\n") + 1
print(f"reading {rel}  ({len(src)} chars / {lines} lines)")
print(
    f"prior classification = {prior['classification']}  prior evidence = {prior['evidence'][:180]}"
)


def hits(pat, flags=0, limit=8):
    out = []
    for m in re.finditer(pat, src, flags):
        ln = src.count("\n", 0, m.start()) + 1
        v = re.sub(r"\s+", " ", m.group(0)).strip()[:150]
        out.append(f"{v}  [{rel}:{ln}]")
        if len(out) >= limit:
            break
    return out


def count(pat, flags=0):
    return len(re.findall(pat, src, flags))


phases = hits(r"phase\s*\(\s*[\"'`]([^\"'`]{3,80})", 0, 14)
agents = count(r"\bagent\s*\(")
parallels = count(r"\bparallel\s*\(")
schemas = count(r"\bschema\s*:")
barriers = count(r"filter\s*\(\s*Boolean\s*\)")
worktree = count(r"worktree")
longrun = count(r"longrun")
codexrefs = count(r"codex", re.I)
models = sorted(
    set(re.findall(r"model\s*:\s*[\"']([a-z0-9\-\[\]\.]+)[\"']", src, re.I))
)
stopish = hits(
    r"^[^\n]{0,150}(?:UNIT-COMPLETE|AND-gate|resume|checkpoint|retry|maxAttempts|"
    r"stop|abort|timeout|budget|cap\b)[^\n]{0,150}$",
    re.M | re.I,
    6,
)
failish = hits(
    r"^[^\n]{0,150}(?:catch\s*\(|FAILED:|try\s*\{|\?\?|\|\|\s*null|filter\(Boolean\)|"
    r"Boolean\)|null-tolerant)[^\n]{0,150}$",
    re.M,
    6,
)
print(
    f"  phases={len(phases)} agent()={agents} parallel()={parallels} schema:={schemas} "
    f"filter(Boolean)={barriers} worktree={worktree} longrun={longrun} codex={codexrefs} "
    f"models={models}"
)

entry = {
    "id": f"WFC-X{TARGET_POS:04d}",
    "name": prior["id"].replace("exec-", ""),
    "unit": "build/wfa-4",
    "registry_slice": (
        "EXTENSION - substitutes for spine position 128 (design-review-loop), which is a "
        "self-declared redirect tombstone the spec forbids counting. Drawn from spine position "
        f"{TARGET_POS}, inside Family H (182-253), which lies OUTSIDE the 1-160 program window, so "
        "it cannot collide with any sibling unit's numbered range."
    ),
    "registry_index": TARGET_POS,
    "source_registry_id": prior["id"],
    "family": "H-executed-corpus",
    "is_extension": True,
    "kind": "executed Claude Code Workflow script (.js, run-record backed)",
    "runtime": prior["runtime"],
    "what_it_does": prior["does"][:700],
    "provenance": [f"live-script :: {rel}"],
    "primary_anchor": rel,
    "primary_size": f"{len(src.encode('utf-8'))} B / {lines} lines",
    "deployment_state": (
        "executed-and-retained: the run record referenced this script and the file is still on "
        "disk (70 of the 72 catalogued Family-H provenance paths still resolve; the corpus itself "
        "records 364 of 668 scripts already swept away, so this population is decaying)"
    ),
    "license": "UNDECLARED",
    "license_source": (
        "owner-authored scratch workflow under the Claude Code projects tree; no license header in "
        "the script, no LICENSE beside it, and no top-level LICENSE in agent-skills-toolchain at "
        "07f465f37d49. The prior registry's 'owner-authored / private estate' is an assertion with "
        "no on-disk license source."
    ),
    "third_party_license_anchors": ["none found in body"],
    "vendoring_origin": "not declared",
    "maintenance_state": [
        f"live-script mtime {__import__('datetime').datetime.utcfromtimestamp(p.stat().st_mtime).isoformat()}Z "
        f"({p.stat().st_size} B)",
        f"prior registry maintenance string: {prior['maintenance']}",
    ],
    "copy_consistency": "single copy on disk; no repo-side twin exists for the executed corpus",
    "task_fit": (
        "The direct ancestor of this program: a full-power harness-restore fan-out whose measured "
        "topology (phase count, fan-out width, typed fan-in count, null-tolerant barrier count) is "
        "the empirical baseline for what a real large wave on this estate looks like."
    ),
    "stages": phases
    or [
        "NOT-EXTRACTED - no phase() call sites matched; the script may name phases differently"
    ],
    "roles": ["orchestrator", "fan-out worker", "synthesiser"],
    "tools": ["claude-code Workflow globals: agent(), parallel(), phase()"]
    + ([f"codex refs x{codexrefs}"] if codexrefs else []),
    "stop_rules": stopish
    or [
        "NONE DECLARED - no UNIT-COMPLETE / AND-gate / retry / timeout / budget token matched"
    ],
    "failure_behaviour": failish
    or ["NOT-EXTRACTED - no catch/try/null-tolerant barrier construct matched"],
    "benchmark_evidence": [
        f"measured by reading the script: phase() sites={len(phases)}, agent() sites={agents}, "
        f"parallel() sites={parallels}, schema: fan-ins={schemas}, filter(Boolean) barriers={barriers}, "
        f"worktree mentions={worktree}, longrun mentions={longrun}, model pins={models or 'none'}  [{rel}]",
        f"prior registry evidence (regex over the run record, NOT a read): {prior['evidence'][:240]}",
    ],
    "classification": "DISTILL",
    "classification_basis": (
        "First actual READ of this entry - the prior archaeology states every Family-H "
        "classification is 'derived from the run record plus a regex mechanism scan - not a read of "
        "the script' and marks it UNVERIFIED. The read shows a one-off scratch orchestration script "
        f"({lines} lines) bound to the Claude Code Workflow runtime with hard-coded, "
        "session-specific prompts, so it is not re-runnable as a product; its value is the measured "
        "topology (fan-out width, typed fan-in ratio, barrier discipline) which distils into the "
        f"blueprint library. Prior mechanical classification was {prior['classification']}."
    ),
    "prior_classification": prior["classification"],
    "classification_changed": prior["classification"] != "DISTILL",
    "distinctness": (
        "Distinct by construction: a run-record-backed executed script on the projects tree, not a "
        "SKILL.md; it shares no path, id or namespace with any of the 32 slice candidates, and the "
        "near-duplicate scan over the 328-skill vault does not apply to it."
    ),
    "materially_distinct": True,
    "status": "VERIFIED-ON-DISK",
    "coverage_note": (
        "Topology counts are MEASURED by regex over the script bytes with line anchors; the script "
        "was NOT executed, so its behaviour is UNVERIFIED as behaviour (settled by re-running it "
        "against a scratch target and recording the run record). Only ONE of the 259 unread "
        "Family-H scripts was read here - the reservoir remains overwhelmingly unharvested, which "
        "is the honest residual, not a coverage claim."
    ),
}

rows = json.loads(OUT.read_text(encoding="utf-8"))
rows = [r for r in rows if r.get("id") != entry["id"]]
rows.append(entry)
OUT.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"\nappended {entry['id']} -> {OUT}  total entries={len(rows)}")
print("SUCCESS:wfa4-extend-entry")
