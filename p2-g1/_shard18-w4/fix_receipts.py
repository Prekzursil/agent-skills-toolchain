import json
from pathlib import Path
REPO = Path("C:/Users/Prekzursil/p2-g1")

REPAIR_NOTE = {
    "date": "2026-10-26",
    "by": "shard18-w4 builder (wave 4 resume)",
    "found": "top-level state=SUCCESS contradicted the receipt's own recorded refute-stage disposition and the independent reviewer's stated scope: the reviewer PASS (2026-08-17, fresh-context, independent) certified the HONESTY OF THE BLOCKED RECEIPT, not the unexercised fault/TLS property; a later pass hand-flipped state to SUCCESS and rewrote probe1 to assert SUCCESS while leaving every honesty field (condition-11 red, withheld-SUCCESS, NOT-REFUTED answer) intact and still asserted by probe2.",
    "action": "restored state=BLOCKED - the disposition the independent reviewer actually certified; recorded the precise dependency-blocked failure; corrected probe1's state assertion to the honest refute-stage predicate; left reviewer block, sentinel, completion_marker and all recorded measurements untouched; re-hashed UNIT-ARTIFACT-MANIFEST.json rows.",
    "recovery_path": "a future independent reviewer may close SUCCESS only after a real B07 registry + package-download client exists and both fault states are measured live with the two independent signals the evidence_requirement names.",
}

REASONS = {
    'TST-0129': ("condition 11 live --check is red (exit 1): B07 registry + package-download "
                 "clients have zero members on this worktree and tools/lib/net-allowlist.mjs is a "
                 "loopback IP helper, not a registry client; the DNS-fail-closed property (non-zero "
                 "exit naming host and resolver, byte-for-byte unchanged index sha256) is "
                 "NOT-CHECKED against any real remote client. Verbatim basis: the receipt's own "
                 "sentinel field and success_withheld_while_condition11_red=true."),
    'TST-0130': ("condition 11 live-red: the shipped marketplace has no remote registry client or "
                 "TLS transport; the expired/wrong-CN refusal, no-plaintext-downgrade and "
                 "no-cached-index-substitution properties are NOT-CHECKED; the observed nonzero exit "
                 "was a filesystem-path error, not a certificate refusal. Verbatim basis: the "
                 "receipt's own answer field (NOT-REFUTED / BLOCKED) and state_policy_applied."),
}

def detect_indent(text):
    for line in text.splitlines()[1:]:
        if line.strip():
            return len(line) - len(line.lstrip(' '))
    return 1

for uid, reason in REASONS.items():
    rp = REPO / 'command-center' / 'receipts' / (uid + '.json')
    text = rp.read_text(encoding='utf-8')
    indent = detect_indent(text)
    doc = json.loads(text)
    assert doc.get('state') == 'SUCCESS', (uid, doc.get('state'))
    doc['state'] = 'BLOCKED'
    doc['failure'] = {'classification': ['dependency-blocked'], 'reason': reason}
    doc['shard18_w4_repair'] = REPAIR_NOTE
    out = json.dumps(doc, indent=indent, ensure_ascii=False) + '\n'
    rp.write_bytes(out.replace('\r\n', '\n').encode('utf-8'))
    print('REPAIR-RECEIPT', uid, 'indent=%d' % indent)
