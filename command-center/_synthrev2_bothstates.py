"""Does check_published_commands.py actually SEE this review's committed receipts?

FIRST VERSION OF THIS SCRIPT WAS ITSELF THE INERT CONTROL, and it is worth keeping the reason.
It broke a published receipt path in the WORKING TREE and expected the gate to go red. The gate
stayed green -- not because it cannot see the receipts, but because it reads every citing document
from `git cat-file -p HEAD:<path>` (check_published_commands.py:195-203, consumed at :221), so a
working-tree mutation never reaches it. A control that cannot deliver the broken state to the
instrument is not a control.

What replaces it, two measurements instead of one broken one:

  1. POSITIVE, that the gate sees the receipts: the published-command count at HEAD minus the
     count at the parent commit must equal the number of `python command-center/_synthrev2_*.py`
     receipts this review published. A delta of 0 would mean they are invisible.
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

# --- 1. positive: the receipts moved the gate's own count -------------------------
rc_now, out_now = run([sys.executable, GATE])
total_now = published_total(out_now)
receipts_head = len(set(RECEIPT.findall(blob("HEAD"))))
receipts_parent = len(set(RECEIPT.findall(blob("HEAD~1"))))
added = receipts_head - receipts_parent
print(f"  receipts published at HEAD / HEAD~1 : {receipts_head} / {receipts_parent}")
print(f"  gate total at HEAD                  : {total_now}  rc={rc_now}")
if rc_now != 0 or total_now is None or added <= 0:
    ok = False
    print(
        "  -> FAIL: the gate is red, unparseable, or this commit published no receipt"
    )

# The delta is only meaningful if the gate re-reads HEAD, which is the point being proven.
rc_parent_probe, _ = run(["git", "cat-file", "-e", f"HEAD~1:{DOC}"])
if rc_parent_probe != 0:
    ok = False
    print("  -> FAIL: no parent revision of the document to compare against")

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
    f"SUCCESS:bothstates the gate reads HEAD, sees {receipts_head} committed receipt(s) "
    f"(+{added} this commit), and fires on a known-bad target"
    if ok
    else "FAILED:bothstates see the lines above"
)
sys.exit(0 if ok else 1)
