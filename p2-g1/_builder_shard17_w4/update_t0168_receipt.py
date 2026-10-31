import json
from pathlib import Path

p = Path("command-center/receipts/TST-0168.json")
r = json.loads(p.read_text(encoding="utf-8"))

r["live_ledger"] = {
    "target": "tools/lib/handled-ledger.mjs",
    "driver": "command-center/p2-wave/probes/TST-0168/live_ledger_refute.mjs",
    "sweep": "command-center/p2-wave/probes/TST-0168/live_ledger_race_sweep.py",
    "raw": "command-center/p2-wave/probes/TST-0168/live-ledger-refute.raw.txt",
    "method": "The child receipt is embedded as the markHandled meta, so exactly one atomic write publishes receipt + ledger row - the receipt-before-ledger crash window that refuted the archived proxy (3/20 cuts) does not exist on this discipline. 20 randomized in-flight suspend points (seeded 0x168CAFE) each kill the dispatcher process (exit 137) mid-walk; a resume process re-derives from the live ledger. Plus both-states arms and 5 randomized SIGKILL chaos kills.",
    "results": {
        "both_states_exactly_once": True,
        "race_points": 20,
        "race_points_exactly_once": 20,
        "chaos_kills": 5,
        "chaos_kills_exactly_once": 5,
        "orphans": 0,
        "missing": 0,
        "duplicate_executions": 0,
        "mutant_control_fired": "2/2 (ignore-handled resume over partial and fully-completed priors double-executes; the exactly-once detector is load-bearing)",
    },
    "verdict": "CONFIRMED",
    "confidence": "almost-certain",
    "single_writer_caveat": "markHandled is read-modify-write; concurrent writers can lose updates. The fan-out shape has ONE dispatcher per state-dir - the discipline the live module itself documents as safe. Multi-writer fan-outs must shard by key or lock above this layer (module docstring, preserved).",
    "measured_at": "2026-10-26 shard17-w4",
}

r["scientific_verdict"] = (
    "ARCHIVED-PROXY-REFUTED (history preserved: receipt-before-ledger window, 3/20 cuts); "
    "LIVE-B07-CONFIRMED (tools/lib/handled-ledger.mjs with receipt-as-meta single atomic write: "
    "exactly-once and zero orphans across 20 randomized cuts + 5 chaos kills; mutant detector fired)"
)
r["question_answer"] = (
    "NO for the archived handled-ledger proxy at 3 of 20 in-flight cuts (history, preserved); "
    "YES for the live B07 target tools/lib/handled-ledger.mjs under the receipt-as-meta single-"
    "atomic-write dispatcher discipline: resume of an in-flight fan-out orphans nothing and "
    "duplicates nothing across every measured cut. SUCCESS withheld pending independent review."
)

r["failure"] = {
    "classification": ["reviewer-absent"],
    "reason": (
        "Built-awaiting-review. The shard19-w4 path-to-green has been executed: the refute was "
        "re-run against the now-existing live target tools/lib/handled-ledger.mjs and the "
        "duplicate-execution finding is resolved there (exactly-once and zero orphans across 20 "
        "randomized cuts, 5 chaos kills, both-states arms; ignore-handled mutant detector fired "
        "2/2). The archived-proxy REFUTED history is preserved verbatim. SUCCESS withheld: "
        "receipt_core forbids state=SUCCESS without reviewer.verdict=PASS + independent=true; "
        "probe1_receipt_integrity asserts the delivered form and stays red until that closure. "
        "Only the independent reviewer closes."
    ),
}
r["reviewer"]["notes"] = (
    "An independent reviewer must re-run the live sweep (command-center/p2-wave/probes/TST-0168/"
    "live_ledger_race_sweep.py - exit 0 this session) plus the two named probes after flipping "
    "state, and confirm the archived-proxy refutation history was preserved, not erased. The "
    "single-writer discipline caveat must be acknowledged in any closure."
)

r["notes"] = (r.get("notes") or "") + (
    " shard17-w4 2026-10-26: executed the recorded path-to-green - live-ledger refute driver + "
    "seeded 20-point race sweep + chaos kills + mutant controls against tools/lib/handled-ledger.mjs "
    "(receipt-as-meta single atomic write): exactly-once everywhere, mutant detector 2/2. Receipt "
    "updated additively (archived-proxy refutation rows untouched so probe2 agreement still holds); "
    "corrupt placeholder failure.reason/reviewer.notes replaced with precise content. State stays "
    "BLOCKED reviewer-absent (program contract). Not owner-gated (owner_approval_required=false)."
)

p.write_text(json.dumps(r, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("receipt updated, bytes:", p.stat().st_size)
