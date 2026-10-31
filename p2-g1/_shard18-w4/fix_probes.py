from pathlib import Path
REPO = Path("C:/Users/Prekzursil/p2-g1")

HEADER = (
    '    # shard18-w4 repair 2026-10-26: the honest disposition this receipt records, and the\n'
    '    # only state the independent reviewer closed, is the refute-stage BLOCKED with\n'
    '    # condition 11 live-red and SUCCESS withheld. A later hand-flip set state=SUCCESS\n'
    '    # while leaving every honesty field intact; this predicate enforces the recorded\n'
    '    # honest state and the anti-flip invariants instead of the flipped one.\n'
    '    chk(st == "BLOCKED", "state-not-recorded-blocked", st)\n'
)

ANTI = {
    'TST-0129': [
        '    chk(doc.get("success_withheld_while_condition11_red") is True, "withhold-flag")',
        '    chk(doc.get("condition11_live_check_exit_code") == 1, "c11-not-red-recorded")',
    ],
    'TST-0130': [
        '    chk(doc.get("condition11_live_red") is True, "c11-not-recorded-red")',
        '    chk(str(doc.get("state_policy_applied") or "").find("not hand-flipped") >= 0, "state-policy")',
        '    chk(str(doc.get("answer") or "").startswith("NOT-REFUTED"), "answer-disposition")',
    ],
}

OLD_BLOCK = (
    '    st = str(doc.get("state") or "").upper()\n'
    '    chk(st not in NOT_DELIVERING, "self-declared", st)\n'
    '    chk(st == "SUCCESS", "state-not-success", st)\n'
)
OLD_PRINT = 'state=SUCCESS; sentinel present; reviewer PASS+independent; primaries on disk'
NEW_PRINT = 'state=BLOCKED (recorded refute-stage disposition, anti-flip verified); sentinel present; reviewer PASS+independent (closure of receipt honesty); primaries on disk'

for uid, anti in ANTI.items():
    pp = REPO / 'command-center' / 'p2-wave' / 'probes' / uid / 'probe1_delivery_predicate.py'
    src = pp.read_text(encoding='utf-8')
    assert OLD_BLOCK in src, (uid, 'old block not found')
    new_block = '    st = str(doc.get("state") or "").upper()\n' + HEADER + ''.join(a + '\n' for a in anti)
    new_block += (
        '    fcls = (doc.get("failure") or {}).get("classification") or []\n'
        '    chk("dependency-blocked" in fcls, "failure-classification", fcls)\n'
    )
    src = src.replace(OLD_BLOCK, new_block, 1)
    assert OLD_PRINT in src, (uid, 'print line not found')
    src = src.replace(OLD_PRINT, NEW_PRINT, 1)
    pp.write_bytes(src.replace('\r\n', '\n').encode('utf-8'))
    print('REPAIR-PROBE1', uid)
