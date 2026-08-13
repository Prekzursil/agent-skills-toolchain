#!/usr/bin/env python3
"""Load the fourth signal from COMMITTED DATA instead of a dict literal in the producer.

THE DEFECT THIS CLOSES.  ``rank_disposition.S4_EXECUTED`` was a hand-typed mapping of
server -> (tool, result) sitting inside the very module that certifies the table.  An
earlier verifier flagged it and it stayed: a claim living inside the thing it certifies
cannot be checked against anything, has no date, no author, and no way to say WHICH part
of a proxy server answered.  Moving it into ``s4-evidence.json`` makes each record a dated,
attributed row that the producer READS -- and, being a file, one a reviewer can diff.

WHY (server, backend) AND NOT server.  ``cloud-hub`` is a proxy over ~12 backends and keeps
advertising a dead backend's tools; ``searxng`` executes its tool perfectly while the
instance behind it is unreachable.  A server-keyed field cannot express either, so the audit
had no way to say "the server is up and the capability is not".  That distinction is the
lane's central finding, and it needs a place to live.

FAIL CLOSED, DELIBERATELY.  An absent or malformed evidence file raises; it does NOT
degrade to "no S4 evidence".  Single-signal-verification's rule 6 is explicit that an
undeclared source is ZERO signals rather than one, and the measured version of that bug --
a gate whose missing ``source_probe`` normalised to empty strings and therefore trivially
"differed" from the verifier -- certified corroboration for claims that declared no
measurement at all.  Silence must be loud here.

CONTROLS (``--self-test``): every validation rule is run against a KNOWN-BROKEN fixture and
required to FIRE, then against the good fixture and required to stay SILENT.  A validator
never seen red is indistinguishable from ``return``.

Read-only, pure, committed input only.  Spawns nothing.  Prints no credential value.
"""

from __future__ import annotations

import copy
import json
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE_FILE = "s4-evidence.json"

REQUIRED = (
    "server",
    "backend",
    "tool",
    "verdict",
    "result",
    "backing_resource",
    "measured_utc_date",
    "measured_by",
)
# Enumerated, never a bare tag: a vocabulary the reader has to guess at is the field most
# often dropped or misused.
VERDICTS = frozenset({"live", "degraded", "auth-dead", "dead", "hang"})
# ONLY 'live' means the capability answered.  'degraded' is the trap this file exists for:
# the CALL succeeded and the CAPABILITY did not.
LIVE = frozenset({"live"})
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MIN_RESULT = 12
BYTE_IDENTICAL_CLAIM = "BYTE-IDENTICAL"


class EvidenceError(SystemExit):
    """Raised (as a SystemExit) so a producer importing this cannot swallow it by accident."""


@dataclass(frozen=True)
class Evidence:
    records: tuple[dict[str, Any], ...]
    unprobed: dict[str, Any]
    path: pathlib.Path

    # ------------------------------------------------------------------ views
    def server_calls(self) -> dict[str, tuple[str, str]]:
        """server -> (tool, result) for SERVER-level records; the old S4_EXECUTED shape."""
        return {
            r["server"]: (r["tool"], r["result"])
            for r in self.records
            if r["backend"] is None
        }

    def backends(self, server: str) -> dict[str, dict[str, Any]]:
        """backend -> record for one server (empty when the server is not a proxy)."""
        return {
            r["backend"]: r
            for r in self.records
            if r["server"] == server and r["backend"] is not None
        }

    def dead_backends(self, server: str) -> dict[str, dict[str, Any]]:
        return {
            b: r for b, r in self.backends(server).items() if r["verdict"] not in LIVE
        }

    def shared_dead_resource(self, a: str, b: str) -> str | None:
        """The backing resource BOTH servers were measured non-functional against.

        Returns None when there is none -- which is the answer that must keep the plain
        wording.  ``backing_resource`` is required non-empty on every backend record
        precisely so this can never match two servers on a shared ``None``.
        """
        ra = {r["backing_resource"] for r in self.dead_backends(a).values()}
        rb = {r["backing_resource"] for r in self.dead_backends(b).values()}
        both = sorted(ra & rb)
        return both[0] if both else None

    def unprobed_backends(self, server: str) -> list[str]:
        return list((self.unprobed.get(server) or {}).get("backends") or [])


# ------------------------------------------------------------------- validation
def validate(blob: Any, where: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every way this file could lie, checked.  Raises on the first non-empty problem set."""
    bad: list[str] = []
    if not isinstance(blob, dict):
        raise EvidenceError(f"FAILED:s4-evidence {where} is not a JSON object")
    records = blob.get("records")
    if not isinstance(records, list) or not records:
        raise EvidenceError(
            f"FAILED:s4-evidence {where} has no records -- an empty evidence set is a "
            "violation, not 'nothing measured'"
        )

    seen: dict[tuple[str, str | None], int] = {}
    for i, r in enumerate(records):
        tag = f"record[{i}]"
        if not isinstance(r, dict):
            bad.append(f"{tag} is not an object")
            continue
        missing = [f for f in REQUIRED if f not in r]
        if missing:
            bad.append(f"{tag} missing {missing}")
            continue
        tag = f"{r['server']}/{r['backend'] or '-'}"
        if r["verdict"] not in VERDICTS:
            bad.append(
                f"{tag} unknown verdict {r['verdict']!r}, want one of {sorted(VERDICTS)}"
            )
        if not isinstance(r["result"], str) or len(r["result"].strip()) < MIN_RESULT:
            bad.append(
                f"{tag} result is empty or too short to be evidence ({r['result']!r})"
            )
        if not isinstance(r["tool"], str) or not r["tool"].strip():
            bad.append(
                f"{tag} names no tool -- a call with no tool is not a measurement"
            )
        if not DATE_RE.match(str(r["measured_utc_date"])):
            bad.append(
                f"{tag} measured_utc_date {r['measured_utc_date']!r} is not YYYY-MM-DD"
            )
        if (
            not isinstance(r["measured_by"], str)
            or len(r["measured_by"].strip()) < MIN_RESULT
        ):
            bad.append(f"{tag} measured_by is empty -- an unattributed measurement")
        # A backend record with no backing_resource would let shared_dead_resource() match
        # two unrelated servers on a shared None and emit a false 'same dead instance'
        # sentence.  Require it rather than defend against it downstream.
        if r["backend"] is not None and not (r["backing_resource"] or "").strip():
            bad.append(f"{tag} backend record has no backing_resource")
        key = (r["server"], r["backend"])
        if key in seen:
            bad.append(f"{tag} duplicate key, already defined at record[{seen[key]}]")
        seen[key] = i

    # A record whose PROSE claims byte-identity must actually be byte-identical to another
    # record's captured response.  This is the C2 overclaim class caught mechanically: the
    # sentence is only allowed to say it if the bytes back it.
    bodies = [r.get("response_body") for r in records if isinstance(r, dict)]
    for r in records:
        if not isinstance(r, dict) or BYTE_IDENTICAL_CLAIM not in str(
            r.get("result", "")
        ):
            continue
        body = r.get("response_body")
        tag = f"{r.get('server')}/{r.get('backend') or '-'}"
        if not body:
            bad.append(
                f"{tag} claims {BYTE_IDENTICAL_CLAIM} but captured no response_body"
            )
        elif sum(1 for b in bodies if b == body) < 2:
            bad.append(
                f"{tag} claims {BYTE_IDENTICAL_CLAIM} but no other record carries the "
                "same bytes -- the sentence is wider than its evidence"
            )

    if bad:
        raise EvidenceError(
            f"FAILED:s4-evidence {where} invalid:\n  " + "\n  ".join(bad)
        )
    return records, blob.get("unprobed") or {}


def load(base: pathlib.Path | None = None) -> Evidence:
    path = (base or HERE) / EVIDENCE_FILE
    if not path.exists():
        raise EvidenceError(
            f"FAILED:s4-evidence {path} is missing -- refusing to run with zero S4 "
            "evidence (an absent source is zero signals, not 'none measured')"
        )
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvidenceError(
            f"FAILED:s4-evidence {path} is not valid JSON: {exc}"
        ) from exc
    records, unprobed = validate(blob, str(path))
    return Evidence(records=tuple(records), unprobed=unprobed, path=path)


# -------------------------------------------------------------------- self-test
_GOOD: dict[str, Any] = {
    "records": [
        {
            "server": "srv",
            "backend": None,
            "tool": "whoami",
            "verdict": "live",
            "result": "answered with an identity",
            "backing_resource": None,
            "response_body": None,
            "measured_utc_date": "2026-08-13",
            "measured_by": "self-test fixture author",
            "corroboration": None,
        },
        {
            "server": "srv",
            "backend": "b1",
            "tool": "ping",
            "verdict": "dead",
            "result": "backend refused the connection",
            "backing_resource": "http://127.0.0.1:1",
            "response_body": "identical-bytes",
            "measured_utc_date": "2026-08-13",
            "measured_by": "self-test fixture author",
            "corroboration": None,
        },
        {
            "server": "other",
            "backend": "b1",
            "tool": "ping",
            "verdict": "dead",
            "result": "backend refused; response is BYTE-IDENTICAL to srv's",
            "backing_resource": "http://127.0.0.1:1",
            "response_body": "identical-bytes",
            "measured_utc_date": "2026-08-13",
            "measured_by": "self-test fixture author",
            "corroboration": None,
        },
    ],
    "unprobed": {"srv": {"backends": ["b2"]}},
}


def _mutate(fn) -> dict[str, Any]:
    blob = copy.deepcopy(_GOOD)
    fn(blob)
    return blob


MUTATIONS = {
    "no records at all": lambda b: b.update(records=[]),
    "missing a required field": lambda b: b["records"][0].pop("measured_by"),
    "verdict outside the vocabulary": lambda b: b["records"][0].update(
        verdict="probably-fine"
    ),
    "empty result sentence": lambda b: b["records"][0].update(result="ok"),
    "unattributed measurement": lambda b: b["records"][0].update(measured_by=""),
    "undated measurement": lambda b: b["records"][0].update(
        measured_utc_date="yesterday"
    ),
    "no tool named": lambda b: b["records"][0].update(tool="  "),
    "duplicate (server, backend) key": lambda b: b["records"].append(
        copy.deepcopy(b["records"][1])
    ),
    "backend record with no backing_resource": lambda b: b["records"][1].update(
        backing_resource=None
    ),
    "byte-identity claimed with no body": lambda b: b["records"][2].update(
        response_body=None
    ),
    "byte-identity claimed, bytes differ": lambda b: b["records"][2].update(
        response_body="different-bytes"
    ),
}


def self_test() -> int:
    print("== s4_evidence self-test (each rule: FIRES broken, SILENT good) ==")
    problems: list[str] = []

    try:
        validate(copy.deepcopy(_GOOD), "<good fixture>")
        print("  ok  baseline good fixture -> silent")
    except SystemExit as exc:
        print(f"  BAD baseline is already red: {exc}")
        return 1

    for label, mut in MUTATIONS.items():
        try:
            validate(_mutate(mut), "<mutant>")
        except SystemExit:
            print(f"  ok  {label:42} -> fired")
            continue
        print(f"  BAD {label:42} -> SURVIVED")
        problems.append(label)

    # The missing-FILE path is a different branch from the malformed-CONTENT path and has
    # its own way of failing open, so it gets its own both-states pair.
    try:
        load(pathlib.Path(__file__).resolve().parent / "_no_such_dir_")
        print("  BAD missing evidence file -> SURVIVED")
        problems.append("missing evidence file")
    except SystemExit:
        print(f"  ok  {'missing evidence file':42} -> fired")

    # And the shipped file must actually load, or the controls above are theatre.
    ev = load()
    if not ev.server_calls():
        problems.append("shipped evidence carries zero server-level calls")
    shared = ev.shared_dead_resource("searxng", "search-hub")
    negative = ev.shared_dead_resource("searxng", "cloud-hub")
    print(
        f"  ok  shipped file loads: {len(ev.records)} records, "
        f"{len(ev.server_calls())} server-level, "
        f"{len(ev.backends('cloud-hub'))} cloud-hub backends"
    )
    # shared_dead_resource is load-bearing for the DISABLE sentence, so it needs BOTH
    # directions: a true pair that matches, and a false pair that must NOT.
    if shared != "http://127.0.0.1:8890":
        problems.append(
            f"searxng/search-hub shared dead resource != expected ({shared!r})"
        )
    if negative is not None:
        problems.append(
            f"searxng/cloud-hub share no dead resource but matched {negative!r} -- "
            "the predicate matches things it should not"
        )
    print(
        f"  {'ok ' if not problems else 'BAD'} shared-dead-resource: positive={shared!r} "
        f"negative={negative!r}"
    )

    if problems:
        for p in problems:
            print(f"  FAIL {p}")
        print(f"FAILED:s4-evidence self-test {len(problems)} problem(s)")
        return 1
    print(
        f"SUCCESS:s4-evidence self-test {len(MUTATIONS) + 1}/{len(MUTATIONS) + 1} rules "
        f"fired on their broken state, shipped file valid ({len(ev.records)} records)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(
        self_test() if "--self-test" in sys.argv or len(sys.argv) == 1 else 0
    )
