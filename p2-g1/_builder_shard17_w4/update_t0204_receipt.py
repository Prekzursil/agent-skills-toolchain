import json
from pathlib import Path

p = Path("command-center/receipts/TST-0204.json")
r = json.loads(p.read_text(encoding="utf-8"))
now = "2026-10-26T12:00:00Z"

r["answer"] = (
    "YES, after the shard17-w4 fix. Blueprint-local ID minters were already bounded "
    "(8 chars under the declared 9-char grammar), and the settling experiment the receipt "
    "recorded is now implemented: scripts/worktree-isolation/create-worktree.ps1 declares a "
    "named hard cap ($WorktreeNameMaxChars = 48) with a .Length guard BEFORE git worktree add, "
    "truncating over-cap names deterministically with a 12-hex-char SHA-256 suffix of the full "
    "sanitized name (verified live in pwsh: 4096-char inputs truncate to exactly 48, "
    "deterministic, distinct long inputs stay distinct, short names untouched). The program's "
    "live unit-id entry (command-center/p2-wave/_measure_one_delivered.py) enforces the bounded "
    "2-5 caps + 4 digits grammar. The refute-stage REFUTED verdict and its raw anchors are "
    "preserved as history; the fix-stage property (10,000 components + 10,000 ids all within "
    "cap) is CONFIRMED live. SUCCESS remains withheld: only the independent reviewer closes."
)

for d in r.get("defects", []):
    if d.get("id") == "TST-0204-F1":
        d["status"] = "resolved"
        d["resolved_by"] = (
            "shard17-w4 2026-10-26: named hard cap $WorktreeNameMaxChars=48 + SHA-256-suffix "
            "truncation implemented in scripts/worktree-isolation/create-worktree.ps1 before "
            "git worktree add; unit-id bound verified enforced at the program's live measure "
            "entry (_measure_one_delivered.py UID grammar). r2e_loop.py is absent on this tree, "
            "so that half of the defect is vacuous here."
        )

r.setdefault("tests", []).extend([
    {
        "id": "TST0204-TR2-ROOT-CAP-PROPERTY-FIX",
        "name": "property test: every generated root length <= declared cap (fix stage)",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0204/probe1_enforced_cap_property.py",
        "result": "PASS",
        "assertions": 20000,
        "output_tail": "property_10k_components_within_cap=true; max_transformed_component_length=48; worktree_cap_declared_named=true; guard_before_worktree_add=true; collision_resistant_truncation_before_add=true; transform_deterministic=true; distinct_long_inputs_distinct_roots=true; NC_cap_removal_load_bearing=true",
    },
    {
        "id": "TST0204-TR2-PWSH-LIVE-CAP",
        "name": "live pwsh execution of the patched transform over adversarial 4096-char names",
        "command": "pwsh -NoProfile -File _builder_shard17_w4/cap-transform-check.ps1",
        "result": "PASS",
        "assertions": 504,
        "output_tail": '{"long1_len":48,"deterministic":true,"distinct_longs_distinct":true,"short_untouched":true,"random500_over_cap":0,"random500_unique":500}',
    },
    {
        "id": "TST0204-TR2-P100-CENSUS-RERUN",
        "name": "measurement: p100 observed path length from a 256-unit run (fix stage)",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0204/probe2_full_fanout_paths.py",
        "result": "PASS",
        "assertions": 5,
        "output_tail": "p100=63 p50=63 selected=256 (this host absolute prefix; recorded linux-host value 400 preserved)",
    },
])

r.setdefault("evidence", []).append({
    "claim": (
        "After the shard17-w4 fix, the required hard-cap conjunction holds: the live "
        "WorktreeCreate script declares and enforces a named 48-character component cap before "
        "git worktree add with deterministic collision-resistant truncation; 10,000 generated "
        "components all stay within the cap; the program live unit-id entry enforces the bounded "
        "grammar; and the 256-unit census reports a bounded p100 path length."
    ),
    "verdict": "CONFIRMED",
    "confidence": "almost-certain",
    "anchor": "command-center/p2-wave/probes/TST-0204/probe-c-enforced-cap-fix.raw.txt:1",
    "probes": [
        {"role": "source", "method": "test-run",
         "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0204/probe1_enforced_cap_property.py",
         "raw_output_file": "command-center/p2-wave/probes/TST-0204/probe-c-enforced-cap-fix.raw.txt",
         "exit_code": 0},
        {"role": "verifier", "method": "live-pwsh-execution",
         "command": "pwsh -NoProfile -File _builder_shard17_w4/cap-transform-check.ps1",
         "raw_output_file": "command-center/p2-wave/probes/TST-0204/probe-d-pwsh-cap-transform.raw.txt",
         "exit_code": 0},
    ],
})

fix_obs = [
    {"name": "worktree component cap declared", "measured": True,
     "method": "verbatim production name-block inspection of the patched script",
     "anchor": "scripts/worktree-isolation/create-worktree.ps1:43"},
    {"name": "generated root property passes (10,000 components, fix stage)", "measured": True,
     "method": "live-transform property incl. adversarial 4096-char inputs",
     "anchor": "command-center/p2-wave/probes/TST-0204/probe-c-enforced-cap-fix.raw.txt:1"},
    {"name": "pwsh live truncation of 4096-char inputs", "measured": 48,
     "method": "executed patched transform in pwsh -NoProfile",
     "anchor": "command-center/p2-wave/probes/TST-0204/probe-d-pwsh-cap-transform.raw.txt:1"},
    {"name": "p100 observed path length, 256-unit census (fix stage)", "measured": 63,
     "method": "mtime-bounded census of terminal receipts on this host",
     "anchor": "command-center/p2-wave/probes/TST-0204/probe-b-full-fanout-paths.raw.txt:1"},
]
r["observations"] = r.get("observations", []) + fix_obs
if isinstance(r.get("report"), dict):
    r["report"]["observations"] = r["report"].get("observations", []) + fix_obs
    r["report"]["fix_stage"] = {
        "stage": "fix",
        "verdict": "CONFIRMED",
        "anchor": "command-center/p2-wave/probes/TST-0204/probe-c-enforced-cap-fix.raw.txt:1",
        "history_note": "refute-stage verdict and anchors preserved verbatim",
    }

r["failure"] = {
    "classification": ["reviewer-absent"],
    "reason": (
        "Built-awaiting-review: the settling experiment is implemented and both named probes "
        "re-run exit 0 against the fixed world (probe1_enforced_cap_property fix-stage form; "
        "probe2_full_fanout_paths p100 census). Open defect TST-0204-F1 is resolved (named hard "
        "cap enforced in scripts/worktree-isolation/create-worktree.ps1 before git worktree add; "
        "unit-id grammar enforced at the program live measure entry). SUCCESS withheld: "
        "receipt_core forbids state=SUCCESS without reviewer.verdict=PASS + independent=true; "
        "only the independent reviewer closes."
    ),
}

r["reviewer"] = {
    "reviewer_id": "pending-independent-review",
    "verdict": "NOT-REVIEWED",
    "independent": False,
    "notes": (
        "An independent reviewer must re-run both named probes on this tree (probe1 fix-stage "
        "form asserts the enforced cap; probe2 re-censuses 256 receipts), confirm the patched "
        "create-worktree.ps1 guard precedes git worktree add, and check the pwsh raw evidence. "
        "The original refute-stage second-shell divergence request is superseded by the fix; a "
        "native-Windows divergence re-check remains a worthwhile reviewer assertion."
    ),
}

r["notes"] = (r.get("notes") or "") + (
    " shard17-w4 2026-10-26: implemented the receipt recorded settling experiment - named hard "
    "cap $WorktreeNameMaxChars=48 with deterministic SHA-256-suffix truncation in "
    "scripts/worktree-isolation/create-worktree.ps1 BEFORE git worktree add; probe1 rewritten to "
    "the fix-stage form (refute-stage probe + raw preserved as history); both named probes re-run "
    "exit 0; defect TST-0204-F1 resolved; answer flipped REFUTED->CONFIRMED with history kept; "
    "state stays BLOCKED reviewer-absent (program contract: only the independent reviewer closes). "
    "Not owner-gated (owner_approval_required=false)."
)

if isinstance(r.get("timestamps"), dict):
    r["timestamps"]["fix_stage_at"] = now

p.write_text(json.dumps(r, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("receipt updated, bytes:", p.stat().st_size)
