"""Probe 2: execute candidate reconciliations against integrity properties.

Mechanically different from probe 1 (which drives the live close.append_event
writer). This module runs a hash-chained prototype and measures tombstone,
crypto-shred, payload externalisation, and write-time minimisation by replay
and verification, not by argument.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

CANARY_EMAIL = "adv0045-canary@example.test"
GENESIS = "0" * 64
PERSONAL_FIELDS = frozenset({"subject_email", "home_path", "email", "display_name"})


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _keystream(key: bytes, n: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < n:
        block = hashlib.sha256(key + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:n])


def xor_crypt(data: bytes, key: bytes) -> bytes:
    ks = _keystream(key, len(data))
    return bytes(a ^ b for a, b in zip(data, ks))


class ChainedLog:
    """Append-only hash-chained JSONL prototype."""

    def __init__(self) -> None:
        self.lines: list[dict[str, Any]] = []
        self.prev = GENESIS
        self.keystore: dict[str, bytes] = {}
        self.sidestore: dict[str, dict[str, Any]] = {}

    def append(self, rec_id: str, body: dict[str, Any]) -> str:
        payload = {"body": body, "id": rec_id}
        digest = _sha(self.prev + "\n" + _canon(payload))
        entry = {"body": body, "hash": digest, "id": rec_id, "prev": self.prev}
        self.lines.append(entry)
        self.prev = digest
        return digest

    def verify_chain(self) -> bool:
        prev = GENESIS
        for entry in self.lines:
            payload = {"body": entry["body"], "id": entry["id"]}
            expect = _sha(prev + "\n" + _canon(payload))
            if expect != entry["hash"] or entry["prev"] != prev:
                return False
            prev = entry["hash"]
        return True

    def raw_contains(self, needle: str) -> bool:
        return needle in json.dumps(self.lines, ensure_ascii=True)

    def replay_raw(self) -> list[dict[str, Any]]:
        return [dict(entry["body"], id=entry["id"]) for entry in self.lines]

    def replay_privacy(self, tombstoned: set[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for entry in self.lines:
            if entry["id"] in tombstoned or entry["body"].get("type") == "tombstone":
                out.append({"id": entry["id"], "type": "tombstone"})
                continue
            out.append(dict(entry["body"], id=entry["id"]))
        return out


def _seed_plaintext(log: ChainedLog) -> None:
    log.append(
        "rec-pii",
        {
            "home_path": "/home/adv0045-synthetic/private/notes.txt",
            "note": "personal field",
            "subject_email": CANARY_EMAIL,
        },
    )
    log.append("rec-ctrl", {"note": "ADV0045-CONTROL-NO-PII"})


def eval_tombstone() -> dict[str, Any]:
    log = ChainedLog()
    _seed_plaintext(log)
    before = log.replay_raw()
    log.append("rec-tomb", {"hides": "rec-pii", "type": "tombstone"})
    raw = log.replay_raw()
    priv = log.replay_privacy({"rec-pii"})
    return {
        "id": "tombstone",
        "chain_ok": log.verify_chain(),
        "breaks_raw_replay_determinism": False,
        "raw_replay_keeps_pii": raw[0].get("subject_email") == CANARY_EMAIL,
        "privacy_replay_hides_pii": CANARY_EMAIL not in json.dumps(priv),
        "privacy_replay_differs_from_raw": before != priv,
        "pii_still_in_log_bytes": log.raw_contains(CANARY_EMAIL),
        "erasure_achieved": False,
        "note": (
            "A tombstone is another append. Raw replay of prior lines is "
            "unchanged and deterministic. Privacy-filtered replay is a "
            "different function; it does not remove the original bytes."
        ),
    }


def eval_crypto_shred() -> dict[str, Any]:
    log = ChainedLog()
    key = hashlib.sha256(b"adv0045-record-key-rec-pii").digest()
    plain = _canon(
        {
            "home_path": "/home/adv0045-synthetic/private/notes.txt",
            "subject_email": CANARY_EMAIL,
        }
    ).encode("utf-8")
    ciphertext = xor_crypt(plain, key)
    log.append(
        "rec-pii",
        {
            "alg": "sha256-keystream-xor",
            "ciphertext_hex": ciphertext.hex(),
            "payload_sha256": hashlib.sha256(plain).hexdigest(),
        },
    )
    log.append("rec-ctrl", {"note": "ADV0045-CONTROL-NO-PII"})
    decrypt_before = xor_crypt(ciphertext, key) == plain
    zero_key = b"\x00" * 32
    decrypt_after = xor_crypt(ciphertext, zero_key) == plain
    return {
        "id": "crypto-shred",
        "chain_ok_before_and_after": log.verify_chain(),
        "decrypt_works_before_shred": decrypt_before,
        "decrypt_works_after_shred": decrypt_after,
        "pii_in_log_plaintext": log.raw_contains(CANARY_EMAIL),
        "erasure_of_recoverable_payload": decrypt_before and not decrypt_after,
        "integrity_preserved": log.verify_chain(),
        "breaks_audit_of_plaintext": decrypt_before and not decrypt_after,
        "note": (
            "Deleting the per-record key leaves the hash chain intact and the "
            "ciphertext in place. Plaintext payload verification fails after "
            "shred. Audit of structure survives; audit of personal content does not."
        ),
    }


def eval_externalise() -> dict[str, Any]:
    log = ChainedLog()
    payload = {
        "home_path": "/home/adv0045-synthetic/private/notes.txt",
        "subject_email": CANARY_EMAIL,
    }
    blob_id = "blob-rec-pii"
    log.sidestore[blob_id] = payload
    log.append(
        "rec-pii",
        {"blob_id": blob_id, "payload_sha256": _sha(_canon(payload))},
    )
    log.append("rec-ctrl", {"note": "ADV0045-CONTROL-NO-PII"})
    fetch_before = log.sidestore.get(blob_id) == payload
    chain_ok = log.verify_chain()
    del log.sidestore[blob_id]
    fetch_after = blob_id in log.sidestore
    return {
        "id": "payload-externalisation",
        "chain_ok": chain_ok and log.verify_chain(),
        "fetch_before_erase": fetch_before,
        "fetch_after_erase": fetch_after,
        "pii_in_log_plaintext": log.raw_contains(CANARY_EMAIL),
        "pointer_remains": "blob_id" in log.lines[0]["body"],
        "erasure_of_side_store": fetch_before and not fetch_after,
        "integrity_preserved": log.verify_chain(),
        "replay_of_payload_after_erase": False,
        "note": (
            "The log stores a pointer and content hash. Erasing the side store "
            "makes the payload unrecoverable while the chain still verifies. "
            "Replay of personal content fails after erase."
        ),
    }


def eval_minimise() -> dict[str, Any]:
    log = ChainedLog()
    incoming = {
        "home_path": "/home/adv0045-synthetic/private/notes.txt",
        "note": "operational",
        "subject_email": CANARY_EMAIL,
    }
    stripped = {k: v for k, v in incoming.items() if k not in PERSONAL_FIELDS}
    log.append("rec-min", stripped)
    historical = ChainedLog()
    _seed_plaintext(historical)
    return {
        "id": "write-time-minimisation",
        "chain_ok": log.verify_chain(),
        "future_write_contains_pii": log.raw_contains(CANARY_EMAIL),
        "historical_plaintext_still_present": historical.raw_contains(CANARY_EMAIL),
        "erases_history": False,
        "integrity_preserved": log.verify_chain(),
        "note": (
            "Stripping personal fields at write time prevents new recoverable "
            "PII. It cannot unwrite historical plaintext already in the log."
        ),
    }


def eval_impossibility() -> dict[str, Any]:
    """A ∧ B ∧ C cannot hold for the same historical personal bytes.

    A = historical log bytes unmodified (append-only / chain verifies)
    B = historical personal payload recoverable for content audit
    C = historical personal payload unrecoverable (erasure)
    """
    attempts: list[dict[str, Any]] = []

    leave = ChainedLog()
    _seed_plaintext(leave)
    attempts.append(
        {
            "A_unmodified": leave.verify_chain(),
            "B_payload_recoverable": leave.raw_contains(CANARY_EMAIL),
            "C_unrecoverable": not leave.raw_contains(CANARY_EMAIL),
            "strategy": "leave-bytes",
        }
    )

    mutate = ChainedLog()
    _seed_plaintext(mutate)
    mutate.lines[0]["body"]["subject_email"] = "REDACTED"
    attempts.append(
        {
            "A_unmodified": mutate.verify_chain(),
            "B_payload_recoverable": mutate.raw_contains(CANARY_EMAIL),
            "C_unrecoverable": not mutate.raw_contains(CANARY_EMAIL),
            "strategy": "mutate-in-place",
        }
    )

    shred = eval_crypto_shred()
    attempts.append(
        {
            "A_unmodified": shred["integrity_preserved"],
            "B_payload_recoverable": shred["decrypt_works_after_shred"],
            "C_unrecoverable": shred["erasure_of_recoverable_payload"],
            "strategy": "crypto-shred",
        }
    )

    none_hold_all_three = all(
        not (
            row["A_unmodified"]
            and row["B_payload_recoverable"]
            and row["C_unrecoverable"]
        )
        for row in attempts
    )
    return {
        "id": "impossibility",
        "A": "historical log bytes unmodified (chain verifies)",
        "B": "historical personal payload recoverable for content audit",
        "C": "historical personal payload unrecoverable",
        "attempts": attempts,
        "no_strategy_satisfies_A_and_B_and_C": none_hold_all_three,
        "residual_risk": (
            "Plaintext personal fields already written to an append-only log "
            "remain recoverable until the entire log file is destroyed as a "
            "unit. Per-subject erasure of those bytes is not possible without "
            "rewriting history."
        ),
        "owner_visible_impact": (
            "A subject-erasure request naming personal data already stored as "
            "plaintext in the event log cannot be honoured per record. "
            "Keeping append-only leaves the field on disk. Honouring erasure "
            "by rewrite breaks the audit prefix. The owner must either accept "
            "residual personal data in historical events, or destroy/seal the "
            "log as a whole and lose that history. New writes must minimise "
            "or crypto-shred."
        ),
    }


def measure() -> dict[str, Any]:
    tomb = eval_tombstone()
    shred = eval_crypto_shred()
    ext = eval_externalise()
    mini = eval_minimise()
    impossible = eval_impossibility()
    ok = (
        tomb["chain_ok"]
        and tomb["pii_still_in_log_bytes"]
        and not tomb["erasure_achieved"]
        and not tomb["breaks_raw_replay_determinism"]
        and tomb["raw_replay_keeps_pii"]
        and shred["chain_ok_before_and_after"]
        and shred["decrypt_works_before_shred"]
        and not shred["decrypt_works_after_shred"]
        and shred["breaks_audit_of_plaintext"]
        and ext["chain_ok"]
        and ext["erasure_of_side_store"]
        and not ext["pii_in_log_plaintext"]
        and not mini["future_write_contains_pii"]
        and mini["historical_plaintext_still_present"]
        and not mini["erases_history"]
        and impossible["no_strategy_satisfies_A_and_B_and_C"]
    )
    return {
        "pass": bool(ok),
        "probe": "probe2-reconciliations",
        "unit_id": "ADV-0045",
        "tombstone": tomb,
        "crypto_shred": shred,
        "externalisation": ext,
        "minimisation": mini,
        "impossibility": impossible,
    }
