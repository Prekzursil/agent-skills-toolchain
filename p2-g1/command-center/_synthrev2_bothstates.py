"""Does check_published_commands.py actually SEE this review's committed receipts?

FIRST VERSION OF THIS SCRIPT WAS ITSELF THE INERT CONTROL, and it is worth keeping the reason.
It broke a published receipt path in the WORKING TREE and expected the gate to go red. The gate
stayed green -- not because it cannot see the receipts, but because it reads every citing document
from `git cat-file -p HEAD:<path>` (check_published_commands.py:195-203, consumed at :221), so a
working-tree mutation never reaches it. A control that cannot deliver the broken state to the
instrument is not a control.

What replaces it, two measurements instead of one broken one:

  1. POSITIVE, that the gate sees the receipts: they are published in the HEAD blob of the
     document, every target resolves in `git ls-files`, and the gate is green.
     THE FIRST DRAFT OF THIS CHECK WAS ALSO WRONG -- it asserted a HEAD-vs-HEAD~1 count delta,
     which is true exactly once, so the probe went red on its very next run. A committed probe
     that stands permanently red trains you to ignore its output (CL9). The delta is now
     REPORTED, anchored to the commit that introduced the receipts, and not asserted on.
  2. FIRE-ON-BROKEN, delegated to the instrument that can actually stage one: the gate ships
     `--self-test`, which synthesises a known-bad target with a runtime-random sentinel and asserts
     `known_bad_is_flagged` and `states_distinguishable`. Reading your own instrument beats
     hand-rolling a worse one.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE = "command-center/slop-report/check_published_commands.py"
DOC = "command-center/GRIND-STATUS.md"
RECEIPT = re.compile(r"python command-center/_synthrev2_[a-z]+\.py")


def run(args):
    p = subprocess.run(
        args, cwd=str(REPO), capture_output=True, text=True, errors="replace"
    )
    return p.returncode, (p.stdout + p.stderr).replace("\r\n", "\n")


def blob(rev):
    p = subprocess.run(
        ["git", "cat-file", "-p", f"{rev}:{DOC}"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        errors="replace",
    )
    return p.stdout if p.returncode == 0 else ""


def published_total(out):
    m = re.search(r"==\s*(\d+)\s+published commands", out)
    return int(m.group(1)) if m else None


ok = True

# --- 1. positive: the receipts are in the gate's HEAD corpus and resolve ----------
# A HEAD-vs-HEAD~1 delta is true exactly once, so asserting on it would make this probe a
# STANDING FALSE RED from its second run onward -- the failure mode CL9 warns about. The
# stable invariant is: the receipts are published at HEAD, every target is tracked, and the
# gate is green. The one-time delta is reported against the commit that introduced them.
rc_now, out_now = run([sys.executable, GATE])
total_now = published_total(out_now)
head_receipts = sorted(set(RECEIPT.findall(blob("HEAD"))))
rc_ls, tracked_out = run(["git", "ls-files"])
tracked = set(tracked_out.split("\n"))
unresolved = [r for r in head_receipts if r.split(" ", 1)[1] not in tracked]
print(f"  receipts published at HEAD          : {len(head_receipts)}")
print(f"  of those NOT tracked                : {len(unresolved)} {unresolved}")
print(f"  gate total at HEAD                  : {total_now}  rc={rc_now}")
if rc_now != 0 or total_now is None or not head_receipts or unresolved:
    ok = False
    print(
        "  -> FAIL: gate red/unparseable, no receipt published, or a target is untracked"
    )

# one-time delta, anchored to the introducing commit rather than to HEAD~1
_, first_out = run(
    ["git", "log", "--reverse", "--format=%H", "-S", head_receipts[0], "--", DOC]
    if head_receipts
    else ["git", "rev-parse", "HEAD"]
)
first = first_out.split("\n")[0].strip()
if first:
    before = len(set(RECEIPT.findall(blob(first + "~1"))))
    print(f"  introduced by {first[:8]}: {before} -> {len(head_receipts)} receipts")

# --- 2. fire-on-broken, from the gate's own shipped control -----------------------
rc_st, out_st = run([sys.executable, GATE, "--self-test"])
fires = out_st.count("ok  known_bad_is_flagged") > 0
disc = out_st.count("ok  states_distinguishable") > 0
print(
    f"  gate --self-test                    : rc={rc_st} known_bad_is_flagged={fires} "
    f"states_distinguishable={disc}"
)
if rc_st != 0 or not (fires and disc):
    ok = False
    print("  -> FAIL: the gate's own both-states control did not discriminate")

print(
    f"SUCCESS:bothstates the gate reads HEAD, sees {len(head_receipts)} committed receipt(s), "
    f"every target tracked, and fires on a known-bad target"
    if ok
    else "FAILED:bothstates see the lines above"
)
sys.exit(0 if ok else 1)
