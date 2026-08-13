#!/usr/bin/env python3
"""Join every measured signal into ONE ranked KEEP / DISABLE / INVESTIGATE table.

Four signals, joined and NEVER collapsed into a single boolean.  Collapsing them is the
measured error the grounding lane quantified: reading ``claude mcp list`` as a mount
signal over-counts the live fleet 2.3x (53 "Connected" vs 23 actually mounted).

  config_state     S1  mcpctl over the 5 on-disk JSON scopes  -- "what the config says"
  host_reachable   S2  ``claude mcp list``                    -- "can a fresh process connect"
  session_mounted  S3  the mcp__* namespaces in this session  -- "can the model see it"
  call_verified    S4  a real call succeeded, by EITHER method -- see the SCOPE below

S4 HAS TWO METHODS AND THE ROW CARRIES BOTH.  A stdio server is verified by a real
``initialize`` + ``tools/list`` handshake (``handshake_verified``); an HTTP-transport
server cannot be spawned at all, so it is verified by a real in-session tool call
(``s4_executed``).  ``call_verified`` is their union and ``call_method`` names which one
answered.

  ROUND 1 SHIPPED THIS WRONG AND A VERIFIER CAUGHT IT.  The legend said "real
  initialize+tools/list, or a real in-session tool call" while the field was computed
  from the handshake ALONE, so five rows (agent-mail, basic-memory, figma, github,
  huggingface) carried ``call_verified: false`` next to their own non-null
  ``s4_executed`` evidence, and the prose said 21/23 while the machine-readable field
  said 16.  The refuted wording is recorded rather than deleted, and
  ``assert_signal_consistency()`` now makes that shape UNREPRESENTABLE.

  ROUND 2's FIX MOVED THE CONTRADICTION INSTEAD OF ENDING IT.  Widening
  ``call_verified`` to the union left ``last_error`` untouched, so those same five rows
  then shipped ``call_verified: true`` beside ``last_error: "transport='http': no stdio
  command"`` -- verified and failed at once, in the same object, in the very field
  ``mcpctl.matrix.Liveness`` reads.  ``liveness_basis`` now states per row whether a
  child was sampled at all, ``probe_note`` carries the categorical "nothing to spawn"
  case, and ``assert_liveness_consistency()`` makes the round-2 shape unrepresentable
  too.  Two fixes drifting against each other is the SAME failure as a legend drifting
  from its field -- which is why the guard is a machine check and not a better sentence.

DISPOSITION IS AN ALGORITHM, NOT AN OPINION.  ``decide()`` is a pure function of the
joined row plus the exact set arithmetic in overlap-report.json.  ``REMOVE`` is not a
representable outcome -- ``assert_reversible()`` fails the run closed if one appears --
because every recommendation here must be undoable by re-enabling one JSON key.  The
same fail-closed discipline now covers the S4 legend: a row whose ``call_verified``
disagrees with its own evidence aborts the run instead of being written out.

Run::

    python rank_disposition.py -o disposition.json --md ../..//docs/mcp-audit/table.md
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import backend_map  # noqa: E402
import s4_evidence  # noqa: E402
from probe_capability import MOUNTED, load_specs  # noqa: E402

KEEP, DISABLE, INVESTIGATE = "KEEP", "DISABLE", "INVESTIGATE"

# The S4 legend is a module constant so the text that SHIPS and the text the invariant
# CHECKS are the same object.  Round 1's defect was two copies drifting apart.
S4_LEGEND = (
    "S4 union: a real call succeeded by EITHER method -- a stdio "
    "initialize+tools/list handshake, or a real in-session tool call. "
    "Read call_method for which one, handshake_verified/s4_executed for "
    "the halves. Enforced by assert_signal_consistency(). "
    "SCOPE, and it is narrower than 'the server works': call_method="
    "'stdio-handshake' proves the PROCESS starts and ADVERTISES a tool surface; "
    "it does not prove any tool executes. Counter-example executed 2026-08-13 by "
    "the integrate lane -- searxng ships handshake_verified=true with 4 tools, "
    "while a real in-session searxng_instance_info call returned "
    "available=false, its backing instance at 127.0.0.1:8890 unreachable. "
    "call_method='in-session-tool-call' IS the stronger evidence. A consumer "
    "must not read this field as capability-in-use."
)

# Same discipline one level down: the liveness/cost block is measurable ONLY from a stdio
# child, so a row that has none must say so in its own field rather than shipping four
# nulls that a reader cannot tell apart from "measured as zero".
LIVENESS_LEGEND = (
    "Whether pid/rss_bytes/tool_count/name_bytes/schema_bytes on THIS row were "
    "sampled from a real stdio child, or were not measured and why. A row whose "
    "basis starts with 'not-measured:' carries no liveness snapshot and must NOT be "
    "injected into mcpctl.matrix.Liveness. Enforced by "
    "assert_liveness_consistency()."
)

# Servers deliberately NOT given an S4 real call, with the reason.  Recording the reason
# is the difference between a measured gap and a silent one.
S4_DECLINED = {
    "brightdata": "metered third-party API -- a real call bills the owner's account",
    "claude-code-mcp": "a real tool call spawns a whole nested Claude session",
    "paper-search": "every tool is a live network search; handshake covers capability",
    "scholarly-access": "same -- live network search per call",
    "deepwiki": "live network call against a third-party AI service",
    "context7": "live network docs fetch, rate-limited",
    "repomix": "cheapest tool still walks a tree",
}

# Real in-session tool calls (S4) NO LONGER LIVE HERE.  They were a dict literal in this
# module -- a claim living inside the thing that certifies it, with no date, no author, and
# no way to say WHICH backend of a proxy answered.  They are now records in
# ``s4-evidence.json``, loaded by ``s4_evidence.load()``, which fails CLOSED when the file
# is missing rather than degrading to "no S4 evidence measured".
#
# The legend for the per-backend half of that data.  Same discipline as S4_LEGEND: the text
# that SHIPS and the text an invariant CHECKS are one object.
BACKEND_LEGEND = (
    "Per-BACKEND liveness for a proxy row. A server-level signal cannot express "
    "'the server is up and this backend is not', which is exactly what cloud-hub does: "
    "it keeps advertising a dead backend's tools and says so itself -- \"Its other "
    'tools stay listed". probed[] carries one real read-only call per backend with its '
    "verdict; unprobed[] is UNMEASURED and explicitly NOT claimed live. "
    "tools_over_dead_backend is attributed via backend_map, whose C1 completeness "
    "control proves every cloud-hub name classifies; it is null for any server without "
    "such a map -- null means NOT ATTRIBUTED, never zero. A dead backend does not "
    "shrink call_verified: the call really did succeed. It shrinks what that success "
    "is evidence OF."
)


def parse_host_list(path: pathlib.Path) -> dict[str, str]:
    """``claude mcp list`` -> name -> Connected / FAILED."""
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8", errors="replace")
    pat = re.compile(r"^([A-Za-z0-9_.\- ]+?):\s+(.*?)\s+-\s+(.*)$")
    out: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(("Checking", "⚠")):
            continue
        m = pat.match(line)
        if m:
            out[m.group(1)] = "Connected" if "Connected" in m.group(3) else "FAILED"
    return out


def best_capability(paths: list[pathlib.Path]) -> dict[str, dict[str, Any]]:
    """Merge capability runs, preferring a verified row and then the larger surface.

    Two runs of the same server can disagree: ``angr`` reported PASS at 23 s, then
    TIMEOUT under a 45 s budget, then PASS again at 48 s.  A fixed timeout is itself a
    detector with a false-negative rate, so a later FAIL must not overwrite an earlier
    PASS -- the PASS is positive evidence the capability exists.
    """
    best: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not path.exists():
            continue
        blob = json.loads(path.read_text(encoding="utf-8"))
        for row in blob.get("rows", []):
            name = row.get("name")
            prev = best.get(name)
            if prev is None:
                best[name] = row
                continue
            rank = (bool(row.get("call_verified")), row.get("tool_count") or 0)
            prev_rank = (bool(prev.get("call_verified")), prev.get("tool_count") or 0)
            if rank > prev_rank:
                best[name] = row
    return best


DEAD_BACKEND_MARK = "backend measured non-functional"

# Both S4 methods can answer for the SAME server, and until now the field could only name
# one of them: `call_method` was "stdio-handshake" whenever a handshake existed, silently
# discarding the in-session call the legend itself calls the STRONGER evidence.  One object
# computes it so the producer and `assert_signal_consistency()` cannot drift apart -- which
# is the round-1 defect, and duplicating the ternary would have reintroduced it.
BOTH_METHODS = "stdio-handshake+in-session-tool-call"


def call_method_of(handshake: bool, in_session: bool) -> str | None:
    if handshake and in_session:
        return BOTH_METHODS
    if handshake:
        return "stdio-handshake"
    return "in-session-tool-call" if in_session else None


def backend_caveat(row: dict[str, Any]) -> str:
    """The sentence a row with a dead backend is REQUIRED to carry.

    ``assert_backend_consistency()`` refuses to write a row that has a dead backend and
    does not say so, which is what stops the round-1 failure mode (a legend and a field
    drifting apart) from recurring one level down.  The caveat is generated from the same
    block the invariant reads, so the two cannot disagree.
    """
    bl = row.get("backend_liveness")
    if not bl or not bl["dead_backends"]:
        return ""
    dead = ", ".join(bl["dead_backends"])
    over = bl["tools_over_dead_backend"]
    share = (
        f", {over}/{row['tool_count']} advertised tools ({bl['dead_surface_pct']}%)"
        if over is not None
        else ""
    )
    unprobed = (
        f"; {len(bl['unprobed'])} further backend(s) UNMEASURED"
        if bl["unprobed"]
        else ""
    )
    return (
        f" -- SCOPE: the call succeeded, the capability did not. {DEAD_BACKEND_MARK}: "
        f"{dead}{share}{unprobed}"
    )


def decide(
    row: dict[str, Any], eligible: dict[str, str], ev: s4_evidence.Evidence
) -> tuple[str, str]:
    """Pure disposition function -> (disposition, evidence sentence)."""
    name = row["name"]
    if name in eligible:
        container = eligible[name]
        # ROUND-5 OVERCLAIM, FIXED HERE.  This sentence used to end "0 unique -- nothing
        # becomes unreachable".  The set arithmetic was right and the sentence was wider
        # than it: it implies the container still SERVES the capability.  Measured
        # 2026-08-13 -- searxng's 4 tools and search-hub's copies both answer against the
        # same instance, and that instance is unreachable, so BOTH sides are non-functional
        # and there is no failover to fall back to.  The verdict does not move (arguably it
        # strengthens); only the claim is scoped, and it is scoped from DATA, not by hand:
        # shared_dead_resource() returns None for any pair without a jointly-measured dead
        # resource, and the plain wording is then what ships.
        shared = ev.shared_dead_resource(name, container)
        base = (
            f"exact set arithmetic: all {row['tool_count']} tool names are a strict "
            f"subset of {container}'s surface, 0 unique -- so disabling removes no "
            f"REACHABLE capability"
        )
        if shared:
            base += (
                f". The duplicated tools are non-functional on BOTH sides: each was "
                f"measured against the same unreachable {shared}, so this is "
                f"deduplication of a DEAD capability, not a failover to a live one"
            )
        return DISABLE, base + backend_caveat(row)
    if row["handshake_verified"]:
        base = (
            f"real initialize+tools/list returned {row['tool_count']} tools in "
            f"{row['elapsed_ms']}ms"
        )
        # Both methods answering is STRONGER evidence than either alone, and the legend
        # already says the in-session call is the stronger of the two -- so a row that has
        # both must not report only the weaker one.
        if row["s4_executed"]:
            tool, result = row["s4_executed"]
            base += f"; and a real in-session call {tool!r} -> {result}"
        return KEEP, base + backend_caveat(row)
    if row["s4_executed"]:
        tool, result = row["s4_executed"]
        return KEEP, f"real in-session call {tool!r} -> {result}" + backend_caveat(row)
    if row["probe_method"] == "not-spawnable" and not row["s4_executed"]:
        return (
            INVESTIGATE,
            "HTTP transport: no stdio command to spawn, and no real call was made "
            f"({S4_DECLINED.get(name, 'not attempted this round')})",
        )
    return (
        INVESTIGATE,
        f"handshake did not complete: {row.get('last_error') or 'unknown'}",
    )


MEASURED_BASIS = "stdio child sampled at handshake time"
NOT_MEASURED = "not-measured:"
LIVENESS_FIELDS = ("pid", "rss_bytes", "tool_count")


def liveness_view(cap: dict[str, Any]) -> tuple[Any, Any, str]:
    """Split the prober's ``last_error`` into a real error and a categorical note.

    Returns ``(last_error, probe_note, liveness_basis)``.

    ROUND 2 COPIED ``last_error`` STRAIGHT ONTO THE ROW and a round-3 pass caught what
    that produced: five rows a real in-session call had PROVED working shipped
    ``call_verified: true`` beside ``last_error: "transport='http': no stdio command"``.
    That string is not an error -- it is a statement that there is no stdio child to
    probe -- and ``last_error`` is one of the four fields ``mcpctl.matrix.Liveness``
    reads, so injecting such a row would hand ``monitorcore``'s pane a server that is
    simultaneously verified and failed.  The categorical case becomes ``probe_note``;
    ``last_error`` is reserved for a handshake that was ATTEMPTED and FAILED.
    """
    raw = cap.get("last_error")
    if not cap:
        return (
            None,
            None,
            f"{NOT_MEASURED} no capability row was produced for this server",
        )
    if cap.get("pid") is not None:
        # A real error alongside a real sample is NOT silently dropped; the invariant
        # decides whether that combination is representable.
        return raw, None, MEASURED_BASIS
    if cap.get("probe_method") == "not-spawnable":
        return (
            None,
            raw,
            f"{NOT_MEASURED} {raw or 'no stdio command'} -- no child process exists to sample",
        )
    return (
        raw,
        None,
        f"{NOT_MEASURED} the stdio handshake did not complete ({raw or 'unknown'})",
    )


def backend_view(
    name: str, cap: dict[str, Any], tool_count: int | None, ev: s4_evidence.Evidence
) -> dict[str, Any] | None:
    """Per-backend liveness for one row, or None when no backend was ever probed.

    None means "this server has no backend records", NOT "its backends are fine" --
    ``assert_backend_consistency()`` checks that reading, so the null cannot quietly
    become a clean bill of health the way a bare null always does.
    """
    recs = ev.backends(name)
    if not recs:
        return None
    dead = sorted(b for b, r in recs.items() if r["verdict"] not in s4_evidence.LIVE)
    over: int | None = None
    pct: float | None = None
    attribution = (
        f"NOT ATTRIBUTED: no tool->backend map exists for {name!r}, so the advertised "
        "tools cannot be split across its backends. Null is not zero."
    )
    if name == backend_map.PROXY_SERVER:
        names = cap.get("tool_names") or []
        buckets, unclassified = backend_map.bucket(names)
        # Fail closed rather than under-report: an unclassified tail silently shrinks
        # whichever backend owns it, which is exactly how a share becomes fiction.
        if unclassified:
            raise SystemExit(
                f"FAILED:rank-disposition backend_map left {len(unclassified)} "
                f"{name} tool(s) unclassified -- dead-surface share would under-report"
            )
        over = sum(len(buckets.get(b, [])) for b in dead)
        # C3: the same total by an independent route.  Two sums that must agree beats one
        # sum that cannot be wrong in a way anybody would notice.
        independent = sum(1 for t in names if backend_map.classify(t) in set(dead))
        if over != independent:
            raise SystemExit(
                f"FAILED:rank-disposition dead-surface disagreement for {name}: "
                f"{over} != {independent}"
            )
        if tool_count:
            pct = round(100.0 * over / tool_count, 1)
        attribution = (
            "backend_map over the committed tools/list surface (its C1 control proves "
            "every name classifies, C3 that the buckets partition it)"
        )
    return {
        "legend": BACKEND_LEGEND,
        "attribution": attribution,
        "probed": [
            {
                "backend": b,
                "tool": recs[b]["tool"],
                "verdict": recs[b]["verdict"],
                "result": recs[b]["result"],
                "backing_resource": recs[b]["backing_resource"],
                "measured_utc_date": recs[b]["measured_utc_date"],
                "measured_by": recs[b]["measured_by"],
                "corroboration": recs[b].get("corroboration"),
            }
            for b in sorted(recs)
        ],
        "dead_backends": dead,
        "unprobed": sorted(ev.unprobed_backends(name)),
        "tools_over_dead_backend": over,
        "dead_surface_pct": pct,
    }


def assert_backend_consistency(
    rows: list[dict[str, Any]], ev: s4_evidence.Evidence
) -> None:
    """Fail closed when a row's backend block and its own evidence sentence disagree.

    The round-1 defect was a LEGEND and a FIELD drifting apart, and the fix for it was a
    machine check rather than a better sentence.  The same failure is available one level
    down: a row can carry ``call_verified: true`` and a dead backend and read, to any
    consumer, as a working server.  So the caveat is not advisory -- a row with a dead
    backend that does not SAY it has one aborts the run.
    """
    bad: list[str] = []
    for r in rows:
        bl = r.get("backend_liveness")
        name = r["name"]
        if bl is None:
            # A null must mean "nothing probed", never "probed and fine".
            if ev.backends(name):
                bad.append(
                    f"{name}: backend records exist but the row carries no block"
                )
            continue
        if not bl["probed"]:
            bad.append(
                f"{name}: backend block with an empty probed[] -- a null in disguise"
            )
        over, pct = bl["tools_over_dead_backend"], bl["dead_surface_pct"]
        if (over is None) != (pct is None):
            bad.append(f"{name}: tools_over_dead_backend={over} but pct={pct}")
        if over is not None:
            if r["tool_count"] is None or over > r["tool_count"]:
                bad.append(
                    f"{name}: {over} tools over dead backends exceeds the "
                    f"{r['tool_count']} it advertises"
                )
            if over and not bl["dead_backends"]:
                bad.append(
                    f"{name}: {over} dead-backend tools but no dead backend named"
                )
        if bl["dead_backends"] and DEAD_BACKEND_MARK not in (r.get("evidence") or ""):
            bad.append(
                f"{name}: dead backend(s) {bl['dead_backends']} but the evidence "
                "sentence does not disclose them -- verified and non-functional at once"
            )
    if bad:
        raise SystemExit(
            "FAILED:rank-disposition backend self-contradiction:\n  " + "\n  ".join(bad)
        )
    if BACKEND_LEGEND and "UNMEASURED" not in BACKEND_LEGEND:
        raise SystemExit(
            "FAILED:rank-disposition the backend legend stopped distinguishing "
            "unmeasured backends from live ones"
        )


def assert_liveness_consistency(rows: list[dict[str, Any]]) -> None:
    """Fail closed if a row's liveness block contradicts itself or hides a null.

    Four shapes abort the run:

      1. ``last_error`` set on a row whose ``call_verified`` is true -- the round-2
         defect: verified and failed asserted in one object.
      2. a row with no ``liveness_basis`` at all -- silence is the thing being removed.
      3. a basis that claims a measurement while pid/rss_bytes/tool_count are null --
         the "unmeasured renders as nothing" hole ``mcpctl.matrix.Liveness`` documents.
      4. a ``not-measured:`` basis carrying no reason, or sitting on a row that in fact
         has a full snapshot.

    (3) and (4) are deliberately BOTH present: a check that only looked at measured rows
    would pass under either hypothesis for the unmeasured ones, which is precisely how
    round 2's DoD3 reported "per-server context cost measured" while 7 of 23 rows carried
    no cost at all.
    """
    bad: list[str] = []
    for r in rows:
        if r.get("last_error") and r.get("call_verified"):
            bad.append(
                f"{r['name']}: call_verified=True beside last_error="
                f"{r['last_error']!r} -- verified and failed in one row"
            )
        basis = r.get("liveness_basis") or ""
        if not basis:
            bad.append(f"{r['name']}: no liveness_basis (a null with no stated reason)")
            continue
        gaps = [f for f in LIVENESS_FIELDS if r.get(f) is None]
        if basis.startswith(NOT_MEASURED):
            reason = basis[len(NOT_MEASURED) :].strip()
            if not gaps:
                bad.append(
                    f"{r['name']}: basis says not-measured but the row carries a full "
                    f"snapshot {[f'{f}={r.get(f)}' for f in LIVENESS_FIELDS]}"
                )
            if len(reason) < 12:
                bad.append(f"{r['name']}: not-measured with no reason ({basis!r})")
        elif gaps:
            bad.append(
                f"{r['name']}: basis {basis!r} claims a measurement but {gaps} are null"
            )
    if bad:
        raise SystemExit(
            "FAILED:rank-disposition liveness self-contradiction:\n  "
            + "\n  ".join(bad)
        )


def assert_reversible(rows: list[dict[str, Any]]) -> None:
    bad = [
        r["name"] for r in rows if r["disposition"] not in {KEEP, DISABLE, INVESTIGATE}
    ]
    if bad:
        raise SystemExit(f"FAILED:rank-disposition non-reversible disposition on {bad}")


def assert_signal_consistency(rows: list[dict[str, Any]], legend: str) -> None:
    """Fail closed if a row's S4 verdict disagrees with the evidence beside it.

    This is the round-1 defect turned into an invariant.  Three ways the artifact could
    contradict itself, each aborting the run:

      1. ``call_verified`` is not the union of its two methods -- the exact shape the
         verifier found (false next to a non-null ``s4_executed``).
      2. ``call_method`` does not name a method that actually produced evidence.
      3. the legend text no longer advertises BOTH methods, i.e. someone narrowed the
         documented meaning without narrowing the computation (or the reverse).

    (3) matters because the round-1 bug was not a wrong number -- both numbers were
    individually correct.  It was a legend and a field drifting apart, and only a check
    that reads BOTH can catch that.
    """
    bad: list[str] = []
    for r in rows:
        union = bool(r["handshake_verified"]) or bool(r["s4_executed"])
        if bool(r["call_verified"]) != union:
            bad.append(
                f"{r['name']}: call_verified={r['call_verified']} but "
                f"handshake={bool(r['handshake_verified'])} "
                f"in_session={bool(r['s4_executed'])}"
            )
            continue
        expected = call_method_of(bool(r["handshake_verified"]), bool(r["s4_executed"]))
        if r["call_method"] != expected:
            bad.append(f"{r['name']}: call_method={r['call_method']!r} != {expected!r}")
    if bad:
        raise SystemExit(
            "FAILED:rank-disposition S4 signal self-contradiction:\n  "
            + "\n  ".join(bad)
        )
    low = legend.lower()
    if "handshake" not in low or "in-session" not in low:
        raise SystemExit(
            "FAILED:rank-disposition the call_verified legend no longer advertises "
            f"both S4 methods: {legend!r}"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=str(HERE))
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--md", default="")
    args = ap.parse_args(argv)
    base = pathlib.Path(args.base)

    mcpctl_path = base / "mcpctl-matrix.json"
    if not mcpctl_path.exists():
        print("FAILED:rank-disposition mcpctl-matrix.json missing")
        return 1
    mcpctl = json.loads(mcpctl_path.read_text(encoding="utf-8-sig"))
    cfg = {r["name"]: r for r in mcpctl["rows"]}

    host = parse_host_list(base / "claude-mcp-list.txt")
    caps = best_capability(
        [
            # Round-2 sweep FIRST: `best_capability` only overrides on a STRICTLY better
            # rank, so ties keep the earlier path.  The r2 rows are the only ones that
            # carry rss_bytes, and every one of them reproduced its round-1 tool count
            # exactly, so preferring them on a tie loses no evidence.  A round-1 row that
            # is strictly better (verified where r2 flaked) still wins.
            base / "capability-matrix-r2.json",
            base / "capability-matrix.json",
            base / "capability-slowrows.json",
        ]
    )
    overlap_path = base / "overlap-report.json"
    eligible: dict[str, str] = {}
    if overlap_path.exists():
        for pair in json.loads(overlap_path.read_text(encoding="utf-8"))["pairs"]:
            target = pair.get("retirement_eligible")
            if target:
                eligible[target] = pair["b"] if target == pair["a"] else pair["a"]

    specs = load_specs()
    if not caps:
        print("FAILED:rank-disposition zero capability rows (fail closed)")
        return 1

    # S4 comes from a committed, dated, attributed FILE now -- not from a literal in this
    # module.  load() raises when it is absent or malformed; it never returns "nothing".
    ev = s4_evidence.load(base)
    s4_calls = ev.server_calls()

    rows: list[dict[str, Any]] = []
    for name in MOUNTED:
        cap = caps.get(name, {})
        conf = cfg.get(name, {})
        spec = specs.get(name, {})
        env_fields = conf.get("env_fields") or []
        last_error, probe_note, liveness_basis = liveness_view(cap)
        row: dict[str, Any] = {
            "name": name,
            # --- the four never-collapsed signals
            "config_state": conf.get("state", "-absent-"),
            "host_reachable": host.get(name, "-absent-"),
            "session_mounted": name in MOUNTED,
            # S4 is the union of its two methods; the sub-signals stay visible so the
            # union is auditable and can never silently replace either half.
            "call_verified": bool(cap.get("call_verified")) or bool(s4_calls.get(name)),
            "handshake_verified": bool(cap.get("call_verified")),
            "call_method": call_method_of(
                bool(cap.get("call_verified")), bool(s4_calls.get(name))
            ),
            # --- inventory (DoD: scope + source file)
            #
            # LIVE CONFIG FIRST, COMMITTED EVIDENCE AS FALLBACK.  ``load_specs()`` reads
            # ``~/.claude.json`` and ``~/.mcp.json`` -- files that exist only on the box that
            # produced the sweep.  Without the fallback this producer cannot reproduce its own
            # artifact anywhere else: on a CI runner ``specs`` is empty and all 23 rows lose
            # BOTH of DoD1's inventory fields, silently, as nulls.  Measured on Ubuntu 24.04
            # in a full clone: regenerated 27,688 B against a committed 28,636 B, differing on
            # exactly ``definition_scope`` and ``source_file``, 23 rows of 23.
            #
            # The fallback is the round-2 capability sweep, which is COMMITTED and recorded
            # both fields per row at probe time, so the values are the same evidence, not a
            # guess.  Byte-identity of the regenerated artifact is asserted on both platforms
            # by ci_gate.py's determinism check, which is what makes this claim falsifiable
            # rather than an assurance.
            "definition_scope": spec.get("definition_scope")
            or cap.get("definition_scope"),
            "source_file": spec.get("source_file") or cap.get("source_file"),
            "config_basis": conf.get("basis"),
            "transport": cap.get("transport") or conf.get("transport"),
            # --- capability + cost
            "probe_method": cap.get("probe_method"),
            "tool_count": cap.get("tool_count"),
            "name_bytes": cap.get("name_bytes"),
            "schema_bytes": cap.get("schema_bytes"),
            "elapsed_ms": cap.get("elapsed_ms"),
            # pid + rss_bytes are the names mcpctl.matrix.Liveness reads, so a row whose
            # liveness_basis is MEASURED_BASIS is an injectable snapshot.  Round 2 said
            # this of "a row of the shipped table" without qualification; measured in
            # round 3, it holds for the 16 handshake rows and NOT for the other 7, whose
            # snapshot is four nulls.  liveness_basis is what tells the two apart, and
            # assert_liveness_consistency() refuses to write a row that omits it.
            # Both fields describe the probe's child at handshake time; that child was
            # reaped immediately afterwards, so the pid is provenance, not a live handle.
            # commit_bytes is kept alongside because a hub's working set understates it,
            # and both are the DIRECT child only -- lazily spawned backends are charged
            # elsewhere.
            "pid": cap.get("pid"),
            "rss_bytes": cap.get("rss_bytes"),
            "commit_bytes": cap.get("commit_bytes"),
            "last_error": last_error,
            "probe_note": probe_note,
            "liveness_basis": liveness_basis,
            # --- security (names only, never values)
            "env_var_names": [f.get("name") for f in env_fields],
            "env_kinds": sorted({f.get("kind") for f in env_fields if f.get("kind")}),
            "credential_bearing": bool(env_fields),
            "s4_executed": s4_calls.get(name),
            "backend_liveness": backend_view(name, cap, cap.get("tool_count"), ev),
        }
        row["disposition"], row["evidence"] = decide(row, eligible, ev)
        rows.append(row)

    assert_reversible(rows)
    assert_signal_consistency(rows, S4_LEGEND)
    assert_liveness_consistency(rows)
    assert_backend_consistency(rows, ev)
    order = {DISABLE: 0, INVESTIGATE: 1, KEEP: 2}
    rows.sort(
        key=lambda r: (order[r["disposition"]], -(r["tool_count"] or 0), r["name"])
    )

    counts = {d: sum(1 for r in rows if r["disposition"] == d) for d in order}
    print("== disposition ==")
    for r in rows:
        print(
            f"  {r['disposition']:12} {r['name']:22} tools={str(r['tool_count']):>4} "
            f"cfg={r['config_state']:16} host={r['host_reachable']:10} "
            f"call={'Y' if r['call_verified'] else 'n'}({r['call_method'] or '-'})"
        )
    print(f"\n{counts}")

    payload = {
        "report": "mcp-disposition",
        "generated_utc_date": "2026-08-12",
        "reversibility_invariant": (
            "REMOVE is not a representable outcome; every DISABLE is undone by "
            "re-enabling one JSON key. Route disables through mcpapply's "
            "DISABLE_PREFERENCE (project-scoped): a disable written to root "
            "disabledMcpServers hides the tools but does NOT prevent the spawn, so it "
            "saves zero RAM (mcpapply/plan.py SPAWN_PREVENTING)."
        ),
        "signals": {
            "config_state": "mcpctl over 5 JSON scopes",
            "host_reachable": "claude mcp list (NOT a mount signal)",
            "session_mounted": "mcp__* namespaces in the auditing session",
            "call_verified": S4_LEGEND,
            "handshake_verified": "S4a only: stdio initialize+tools/list completed",
            "s4_executed": "S4b only: (tool, result) of a real in-session tool call",
            "call_method": (
                "which S4 method answered, or null if neither. A row where BOTH "
                f"answered reads {BOTH_METHODS!r}: reporting only the handshake "
                "discarded the in-session call the legend itself calls the stronger "
                "evidence."
            ),
            "backend_liveness": BACKEND_LEGEND,
            "liveness_basis": LIVENESS_LEGEND,
            "last_error": (
                "a stdio handshake that was ATTEMPTED and FAILED. Null on a row with "
                "no stdio command at all -- that case is probe_note, because a "
                "categorical 'nothing to spawn' is not a failure of the server."
            ),
            "probe_note": "why no stdio child was attempted (not an error)",
        },
        "refuted_round_1": {
            "claim": (
                "round 1 documented call_verified as 'real initialize+tools/list, or a "
                "real in-session tool call' while computing it from the handshake alone"
            ),
            "verdict": "REFUTED by the round-1 verifier",
            "measured": (
                "5 rows (agent-mail, basic-memory, figma, github, huggingface) had "
                "call_verified=false beside their own non-null s4_executed evidence; "
                "the prose said 21/23 verified while the field summed to 16"
            ),
            "fix": (
                "call_verified is now the union, call_method names the method, and "
                "assert_signal_consistency() aborts the run on the old shape"
            ),
        },
        "refuted_round_2": {
            "claim": (
                "round 2 wrote that disposition.json rows 'now also carry pid + "
                "rss_bytes, so a row of the shipped table IS an injectable snapshot'"
            ),
            "verdict": "REFUTED in round 3",
            "measured": (
                "true for the 16 handshake-verified rows and false for the other 7, "
                "whose pid/rss_bytes/tool_count/name_bytes/schema_bytes are all null; "
                "5 of those 7 additionally shipped call_verified=true beside "
                "last_error=\"transport='http': no stdio command\", so an injected "
                "Liveness would have read verified-and-failed at once"
            ),
            "fix": (
                "every row now carries liveness_basis; the categorical case moved to "
                "probe_note; assert_liveness_consistency() aborts the run on a "
                "verified-and-errored row, a missing basis, a basis that claims a "
                "measurement it does not have, and a reasonless not-measured"
            ),
            "residual": (
                "the 7 rows still have no cost measurement. Settling experiment: an "
                "HTTP initialize+tools/list against each endpoint, or a dump of the "
                "client-side tool registry -- neither is a stdio spawn, so neither is "
                "reachable from this producer as built."
            ),
        },
        "refuted_round_5": {
            "claim": (
                "the DISABLE row for searxng shipped 'all 4 tool names are a strict "
                "subset of search-hub's surface, 0 unique -- nothing becomes unreachable'"
            ),
            "verdict": "REFUTED as an OVERCLAIM; the disposition itself is unchanged",
            "measured": (
                "2026-08-13, real in-session calls to BOTH copies of "
                "searxng_instance_info returned byte-identical available=false against "
                "the same unreachable http://127.0.0.1:8890. The set arithmetic was "
                "correct; the sentence implied search-hub still SERVES the capability, "
                "and it does not -- there is no failover to fall back to"
            ),
            "fix": (
                "the sentence is generated from shared_dead_resource(), which returns "
                "None for any pair without a jointly-measured dead resource and lets the "
                "plain wording ship. The byte-identity claim is itself checked: "
                "s4_evidence.validate() fails closed if a record's prose says "
                "BYTE-IDENTICAL and no other record carries the same captured bytes"
            ),
            "note": (
                "code right, sentence wider than its evidence -- the dominant defect "
                "class in this program, and it does NOT move the verdict"
            ),
        },
        "s4_evidence_source": {
            "path": ev.path.name,
            "records": len(ev.records),
            "server_level": len(s4_calls),
            "why": (
                "S4 used to be a dict literal inside this producer -- a claim living "
                "inside the thing that certifies it, undated, unattributed, and unable "
                "to say which BACKEND of a proxy answered. It is now committed data the "
                "producer reads, and load() fails closed when it is absent rather than "
                "degrading to 'no S4 evidence' (an absent source is zero signals, not one)"
            ),
        },
        "counts": counts,
        "s4_declined": S4_DECLINED,
        "rows": rows,
    }
    if args.out:
        pathlib.Path(args.out).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"wrote {args.out}")
    if args.md:
        pathlib.Path(args.md).write_text(
            render_md(rows, counts), encoding="utf-8", newline="\n"
        )
        print(f"wrote {args.md}")
    print(f"SUCCESS:rank-disposition rows={len(rows)} {counts}")
    return 0


def render_md(rows: list[dict[str, Any]], counts: dict[str, int]) -> str:
    head = (
        "| disposition | server | S1 config | S2 host | S3 mounted | S4 real call | "
        "tools | name B | schema B | evidence |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
    )
    body = []
    for r in rows:
        s4 = (
            "PASS"
            if r["handshake_verified"]
            else ("PASS*" if r["s4_executed"] else "--")
        )
        body.append(
            f"| **{r['disposition']}** | `{r['name']}` | {r['config_state']} | "
            f"{r['host_reachable']} | {'yes' if r['session_mounted'] else 'no'} | {s4} | "
            f"{r['tool_count'] if r['tool_count'] is not None else '--'} | "
            f"{r['name_bytes'] if r['name_bytes'] is not None else '--'} | "
            f"{r['schema_bytes'] if r['schema_bytes'] is not None else '--'} | "
            f"{r['evidence']} |"
        )
    verified = sum(1 for r in rows if r["call_verified"])
    measured = sum(
        1 for r in rows if not (r["liveness_basis"] or "").startswith(NOT_MEASURED)
    )
    tail = (
        f"\n\n`S4 PASS` = stdio initialize+tools/list handshake.  `S4 PASS*` = a real "
        f"in-session tool call instead (HTTP transport cannot be spawned).  Both count "
        f"as S4 `call_verified`, which is their union: {verified}/{len(rows)} rows.  "
        f"Counts: {counts}.\n\n"
        f"A `--` in the cost columns is **not measured**, never zero: cost comes from a "
        f"stdio child and {len(rows) - measured} of {len(rows)} rows have none to sample. "
        f"Each such row states why in its own `liveness_basis`, and "
        f"`assert_liveness_consistency()` refuses to write a null without one.\n"
    )
    return head + "\n".join(body) + tail


if __name__ == "__main__":
    raise SystemExit(main())
