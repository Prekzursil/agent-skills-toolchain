import hashlib, json, re
from pathlib import Path
REPO = Path("C:/Users/Prekzursil/p2-g1")

def digest(p):
    raw = Path(p).read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest(), len(raw)

def detect_indent(text):
    for line in text.splitlines()[1:]:
        if line.strip():
            return len(line) - len(line.lstrip(' '))
    return 1

REPAIR_NOTE = {
    "date": "2026-10-26",
    "by": "shard18-w4 builder (wave 4 resume)",
    "found": "top-level state=SUCCESS contradicted the receipt's own recorded refute-stage disposition and the independent reviewer's stated scope: the reviewer PASS (2026-08-17, fresh-context, independent) certified the HONESTY OF THE BLOCKED RECEIPT, not the unexercised fault/TLS property; a later pass hand-flipped state to SUCCESS and rewrote probe1 to assert SUCCESS while leaving every honesty field (condition-11 red, withheld-SUCCESS, NOT-REFUTED answer) intact and still asserted by probe2.",
    "action": "restored state=BLOCKED - the disposition the independent reviewer actually certified; recorded the precise dependency-blocked failure; corrected probe1's state assertion to the honest refute-stage predicate; left reviewer block, sentinel, completion_marker and all recorded measurements untouched; re-hashed UNIT-ARTIFACT-MANIFEST.json rows.",
    "recovery_path": "a future independent reviewer may close SUCCESS only after a real B07 registry + package-download client exists and both fault states are measured live with the two independent signals the evidence_requirement names.",
}

CFG = {
    'TST-0129': {
        'reason': ("condition 11 live --check is red (exit 1): B07 registry + package-download "
                   "clients have zero members on this worktree and tools/lib/net-allowlist.mjs is a "
                   "loopback IP helper, not a registry client; the DNS-fail-closed property (non-zero "
                   "exit naming host and resolver, byte-for-byte unchanged index sha256) is "
                   "NOT-CHECKED against any real remote client. Verbatim basis: the receipt's own "
                   "sentinel field and success_withheld_while_condition11_red=true."),
        'anti_flip': [
            '    chk(doc.get("success_withheld_while_condition11_red") is True, "withhold-flag")',
            '    chk(doc.get("condition11_live_check_exit_code") == 1, "c11-not-red-recorded")',
        ],
    },
    'TST-0130': {
        'reason': ("condition 11 live-red: the shipped marketplace has no remote registry client or "
                   "TLS transport; the expired/wrong-CN refusal, no-plaintext-downgrade and "
                   "no-cached-index-substitution properties are NOT-CHECKED; the observed nonzero exit "
                   "was a filesystem-path error, not a certificate refusal. Verbatim basis: the "
                   "receipt's own answer field (NOT-REFUTED / BLOCKED) and state_policy_applied."),
        'anti_flip': [
            '    chk(doc.get("condition11_live_red") is True, "c11-not-recorded-red")',
            '    chk(str(doc.get("state_policy_applied") or "").find("not hand-flipped") >= 0, "state-policy")',
            '    chk(str(doc.get("answer") or "").startswith("NOT-REFUTED"), "answer-disposition")',
        ],
    },
}

for uid, cfg in CFG.items():
    rp = REPO / 'command-center' / 'receipts' / (uid + '.json')
    text = rp.read_text(encoding='utf-8')
    indent = detect_indent(text)
    doc = json.loads(text)
    assert doc.get('state') == 'SUCCESS', (uid, doc.get('state'))
    doc['state'] = 'BLOCKED'
    doc['failure'] = {
        'classification': ['dependency-blocked'],
        'reason': cfg['reason'],
    }
    doc['shard18_w4_repair'] = REPAIR_NOTE
    new_text = json.dumps(doc, indent=indent, ensure_ascii=False) + '\n'
    rp.write_bytes(new_text.replace('\r\n', '\n').encode('utf-8'))
    print('REPAIR-RECEIPT', uid, 'indent=%d' % indent)

    pp = REPO / 'command-center' / 'p2-wave' / 'probes' / uid / 'probe1_delivery_predicate.py'
    src = pp.read_text(encoding='utf-8')
    old_block = (
        '    st = str(doc.get("state") or "").upper()\n'
        '    chk(st not in NOT_DELIVERING, "self-declared", st)\n'
        '    chk(st == "SUCCESS", "state-not-success", st)\n'
    )
    new_block = (
        '    st = str(doc.get("state") or "").upper()\n'
        '    # shard18-w4 repair 2026-10-26: the honest disposition this receipt records, and the\n'
        '    # only state the independent reviewer closed, is the refute-stage BLOCKED with\n'
        '    # condition 11 live-red and SUCCESS withheld. A later hand-flip set state=SUCCESS\n'
        '    # while leaving every honesty field intact; this predicate enforces the recorded\n'
        '    # honest state and the anti-flip invariants instead of the flipped one.\n'
        '    chk(st == "BLOCKED", "state-not-recorded-blocked", st)\n'
        + ''.join(line + '\n' for line in cfg['anti_flip']) +
        '    fcls = (doc.get("failure") or {}).get("classification") or []\n'
        '    chk("dependency-blocked" in fcls, "failure-classification", fcls)\n'
    )
    assert old_block in src, (uid, 'old block not found
