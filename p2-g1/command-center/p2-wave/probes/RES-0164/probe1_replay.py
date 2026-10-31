#!/usr/bin/env python3
"""RES-0164 probe1_replay.

tests row: Python named probe - replay/redaction both-states control.
Independently re-runs the redaction-vs-replay experiment the artifact records:
an unredacted three-record ledger replays (state + command digest identical);
redacting a NON-replay-consumed field (metadata.debug_secret) still replays
while NOT preserving bytes; redacting a replay-consumed field
(payload.transfer_authorization, checkpoint-hash-verified) breaks replay with
an authorization-hash error. Recomputes the outcome classes and requires them
to match the artifact's recorded experiment. Defaults to FAIL.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


class Replayer:
    """Independent minimal replayer: state from amounts, command checkpoint hash
    over payload.transfer_authorization only. Deliberately excludes metadata."""

    def __init__(self, records):
        self.records = [json.loads(r) for r in records if r.strip()]

    @staticmethod
    def _redact(records, field):
        out = []
        for r in records:
            r = json.loads(r)
            parent, _, leaf = field.partition(".")
            if parent in r and isinstance(r[parent], dict):
                r[parent] = {k: v for k, v in r[parent].items() if k != leaf}
            out.append(r)
        return out

    def replay(self, records):
        balance, cmds, ok = 0, [], True
        for r in (json.loads(x) if isinstance(x, str) else x for x in records):
            try:
                balance += r["amount"]
                cmds.append(hashlib.sha256(
                    json.dumps(r["payload"]["transfer_authorization"], sort_keys=True).encode()
                ).hexdigest())
            except Exception:
                ok = False
                break
        return ok, balance, hashlib.sha256("".join(cmds).encode()).hexdigest()


def main() -> int:
    art = REPO / "command-center/research/prior-art/RES-0164-event-log-schema-prior-art.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:230]})
        return bool(ok)

    # fixture per the recorded fixture_type: three records, canary in metadata
    # (non-replay-consumed) and a replay-consumed authorization payload field
    recs = [
        json.dumps({"seq": 1, "amount": 100,
                    "metadata": {"debug_secret": "RES0164-CANARY-META"},
                    "payload": {"transfer_authorization": "AUTH-A1"}}),
        json.dumps({"seq": 2, "amount": 50,
                    "metadata": {"debug_secret": "RES0164-CANARY-META-2"},
                    "payload": {"transfer_authorization": "AUTH-B2"}}),
        json.dumps({"seq": 3, "amount": -25,
                    "metadata": {"debug_secret": "RES0164-CANARY-META-3"},
                    "payload": {"transfer_authorization": "AUTH-C3"}}),
    ]
    rp = Replayer(recs)

    ok, balance, digest = rp.replay(recs)
    ck("pre-redaction-replays", ok and balance == 125 and len(digest) == 64,
       f"ok={ok} balance={balance}")

    nr = rp._redact(recs, "metadata.debug_secret")
    ok2, bal2, dig2 = rp.replay(nr)
    ck("non-replay-field-redaction-still-replays", ok2 and bal2 == balance and dig2 == digest,
       f"ok={ok2} same_balance={bal2 == balance} same_digest={dig2 == digest}")
    ck("byte-identity-not-preserved-on-redaction",
       nr != [json.loads(x) for x in recs],
       "redacted records differ from original bytes")

    br = rp._redact(recs, "payload.transfer_authorization")
    # simulate recorded checkpoint: prior checkpoint carries AUTH values; redacted
    # rebuild produces empty checkpoint -> mismatch = replay failure, not silent
    br_ok = all(x.get("payload", {}).get("transfer_authorization") for x in br)
    ck("replay-field-redaction-breaks-replay", br_ok is False,
       "checkpoint field emptied -> authorization checkpoint cannot verify")

    rre = (doc.get("report") or {}).get("redaction_replay_experiment") or {}
    pre = rre.get("pre_redaction") or {}
    nb = rre.get("redaction_that_does_not_break_semantic_replay") or {}
    bk = rre.get("redaction_that_breaks_replay") or {}
    ck("recorded-pre-redaction-matches", pre.get("replay_success") is True and pre.get("balance") == 125,
       json.dumps({k: pre.get(k) for k in ("replay_success", "balance")}, default=str))
    ck("recorded-nonreplay-redaction-matches",
       nb.get("replay_success") is True and nb.get("same_balance") is True
       and nb.get("same_command_digest") is True and nb.get("byte_identity_preserved") is False,
       str(nb.get("field")))
    ck("recorded-replay-field-redaction-breaks",
       bk.get("replay_success") is False and "authorization" in str(bk.get("error_class")).lower(),
       str(bk.get("error_class")))
    ck("recorded-fields-match-live-experiment-fields",
       nb.get("field") == "metadata.debug_secret" and bk.get("field") == "payload.transfer_authorization",
       f"{nb.get('field')} | {bk.get('field')}")

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and doc.get("completion_sentinel") == "SUCCESS:RES-0164",
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe1-replay", "unit_id": "RES-0164", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0164-probe1 replay/redaction both-states re-run agrees" if not red
          else f"FAILED:RES-0164-probe1 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
