# CNF-0015 reviewer step 3: DETECTOR CONTROL RE-RUN (fresh context, claude).
# Runs the shipped both-states suite, the receipt-verified detector directly on
# both fixture states, a gate-form invocation (capture the firing exit code on
# the known-broken fixture), and an INDEPENDENT recomputation of the id sets.
# Appends the full transcript to detector-control-rerun.raw.txt as it goes.
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\agent-skills-toolchain")
PROBE = REPO / "command-center" / "p2-wave" / "probes" / "CNF-0015"
PRE = PROBE / "fixtures" / "pre-fix"
POST = PROBE / "fixtures" / "post-fix"
EVID = REPO / "command-center" / "p2-wave" / "reviews" / "CNF-0015"
RAW = EVID / "detector-control-rerun.raw.txt"

sys.path.insert(0, str(PROBE))


def emit(line: str = "") -> None:
    print(line)
    with RAW.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


RAW.write_text(
    "CNF-0015 independent detector-control re-run\n"
    f"reviewer: claude (fresh context)  started: {datetime.now(timezone.utc).isoformat()}\n"
    f"repo: {REPO}\n"
    "receipt: command-center/confirmation/CNF-0015-blocker-repro.json\n"
    "detector (sha256-verified vs receipt): command-center/p2-wave/probes/CNF-0015/option_id_collision.py\n"
    "known-broken fixture (sha256-verified): fixtures/pre-fix/  known-good: fixtures/post-fix/\n\n",
    encoding="utf-8",
)

emit("=== 3a. shipped both-states suite: pytest -q test_option_id_collision.py ===")
r = subprocess.run(
    [sys.executable, "-m", "pytest", str(PROBE / "test_option_id_collision.py"), "-q"],
    capture_output=True,
    text=True,
    cwd=str(REPO),
    timeout=300,
)
emit(
    "$ python -m pytest command-center/p2-wave/probes/CNF-0015/test_option_id_collision.py -q"
)
emit(r.stdout.strip())
if r.stderr.strip():
    emit("[stderr] " + r.stderr.strip()[:500])
emit(f"pytest exit code: {r.returncode}")
emit()

emit("=== 3b. detector directly on both states (measure_dir) ===")
import option_id_collision as oic  # noqa: E402  (receipt-verified bytes)

pre_rep = oic.measure_dir(PRE)
post_rep = oic.measure_dir(POST)
emit("PRE  (known-broken): " + json.dumps(pre_rep.as_dict()))
emit("POST (known-good)  : " + json.dumps(post_rep.as_dict()))
sample = sorted(pre_rep.family_m_ids & pre_rep.doc13_bare_m_ids)[:8]
emit(f"intersection sample (first 8 of {pre_rep.shared_id_count}): {sample}")
emit()

emit("=== 3c. detector in GATE form on the known-broken fixture (firing exit) ===")
# A detector that 'fails iff the collision is live' must exit non-zero on PRE.
emit(
    '$ python -c "import option_id_collision as o; raise SystemExit(1 if o.collision_is_live(PRE) else 0)"'
)
gate_pre = 1 if oic.collision_is_live(PRE) else 0
gate_post = 1 if oic.collision_is_live(POST) else 0
emit(
    f"gate exit on PRE  (broken): {gate_pre}   -> {'FIRED (RED)' if gate_pre else 'silent'}"
)
emit(
    f"gate exit on POST (fixed) : {gate_post}   -> {'FIRED (RED)' if gate_post else 'silent (green)'}"
)
emit()

emit("=== 3d. INDEPENDENT recomputation (reviewer-written, not the probe's code) ===")


# Different implementation: token scan with manual boundaries, no shared regexes.
def indep_ids(text: str, kind: str) -> set[str]:
    if kind == "family":
        heads = re.findall(r"^#{2,6}\s*`?(M-\d{1,3})`?", text, re.M)
        return set(heads)
    scrub = re.sub(r"MECH-\d{1,3}", "", text)
    return {
        t
        for t in re.findall(r"[A-Za-z]+-\d{1,3}", scrub)
        if re.fullmatch(r"M-\d{1,3}", t)
    }


d07 = (PRE / "07-OPTION-UNIVERSE.md").read_text(encoding="utf-8")
d13pre = (PRE / "13-ARCHITECTURE-CANDIDATES.md").read_text(encoding="utf-8")
d13post = (POST / "13-ARCHITECTURE-CANDIDATES.md").read_text(encoding="utf-8")
dec_pre = (PRE / "17-DECISION-LOG.md").read_text(encoding="utf-8")
dec_post = (POST / "17-DECISION-LOG.md").read_text(encoding="utf-8")
fam = indep_ids(d07, "family")
bare_pre = indep_ids(d13pre, "bare")
bare_post = indep_ids(d13post, "bare")
emit(f"independent family_m_ids(doc07)        : {len(fam)}")
emit(f"independent bare-M(doc13 PRE)          : {len(bare_pre)}")
emit(f"independent |family ∩ bare| PRE        : {len(fam & bare_pre)}")
emit(f"independent bare-M(doc13 POST)         : {len(bare_post)}")
emit(f"independent |family ∩ bare| POST       : {len(fam & bare_post)}")
emit(
    f"independent MECH substr in 17 PRE/POST : {dec_pre.count('MECH')}/{dec_post.count('MECH')}"
)
emit()

verdict_pre = pre_rep.shared_id_count == 31 and pre_rep.collision_live is True
verdict_post = post_rep.shared_id_count == 0 and post_rep.collision_live is False
agree = (len(fam & bare_pre) == pre_rep.shared_id_count) and (len(fam & bare_post) == 0)
emit("=== VERDICT INPUTS ===")
emit(
    f"detector fired on known-broken fixture (shared_id_count=31, collision_live=True, gate exit=1): {verdict_pre and gate_pre == 1}"
)
emit(
    f"detector silent on known-good fixture (shared_id_count=0, collision_live=False, gate exit=0): {verdict_post and gate_post == 0}"
)
emit(f"independent recomputation agrees with detector (31 pre / 0 post): {agree}")
emit(f"shipped pytest suite green with both-states assertions: {r.returncode == 0}")
