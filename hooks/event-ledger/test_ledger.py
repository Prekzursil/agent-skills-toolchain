#!/usr/bin/env python
"""Self-contained tests for the event-ledger keystone. Run: python test_ledger.py
Uses a temp EVENT_LEDGER_ROOT so it never touches real ledgers."""

from __future__ import annotations

import importlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
fails = []


def check(name, cond):
    print(f"  {'OK ' if cond else 'BAD'}  {name}")
    if not cond:
        fails.append(name)


def main():
    tmp = tempfile.mkdtemp(prefix="ledger-test-")
    os.environ["EVENT_LEDGER_ROOT"] = tmp
    sys.path.insert(0, str(HERE))
    import ledger

    importlib.reload(ledger)
    proj = "C:/fake/projectA"

    print("== core append / seq / replay ==")
    e1 = ledger.append(proj, "goal", text="ship the ledger")
    e2 = ledger.append(proj, "turn", head="aaa111", branch="main", dirty_files=2)
    e3 = ledger.append(
        proj, "failure", text="1mcp eager-spawns", preconditions="1mcp<=0.32.2"
    )
    check("seq is monotonic 1,2,3", [e1["seq"], e2["seq"], e3["seq"]] == [1, 2, 3])
    rep = ledger.replay(proj, 10)
    check(
        "replay returns 3 events oldest->newest", [r["seq"] for r in rep] == [1, 2, 3]
    )
    st = ledger.state(proj)
    check("state.goal projected", st["goal"] == "ship the ledger")
    check("state.head projected from turn", st["head"] == "aaa111")
    check(
        "open_failures recorded with preconditions",
        len(st["open_failures"]) == 1
        and st["open_failures"][0]["preconditions"] == "1mcp<=0.32.2",
    )
    check(
        "aliases records the cwd that mapped into this shard",
        proj in (st.get("aliases") or []),
    )

    print("== milestone tombstones a failure (supersedes) ==")
    fseq = st["open_failures"][0]["seq"]
    ledger.append(proj, "milestone", text="upgraded 1mcp", supersedes_failures=[fseq])
    st2 = ledger.state(proj)
    check("failure auto-tombstoned", len(st2["open_failures"]) == 0)

    print("== typed claim-edge store ==")
    required_relations = {
        "supports",
        "contradicts",
        "duplicate_of",
        "supersedes",
        "derived_from",
    }
    # Known-broken before G-04: the typed relation vocabulary is absent.
    check(
        "claim-edge relation vocabulary is exposed",
        required_relations <= set(getattr(ledger, "CLAIM_RELATIONS", ())),
    )

    invalid_note_kind = subprocess.run(
        [
            sys.executable,
            str(HERE / "note.py"),
            "--kind",
            "claim_edge",
            "missing edge schema",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    # Known-broken before G-04: there is no separate public annotation-kind contract.
    check(
        "generic note CLI cannot bypass the claim-edge schema",
        hasattr(ledger, "NOTE_KINDS")
        and "claim_edge" in ledger.KINDS
        and "claim_edge" not in ledger.NOTE_KINDS
        and invalid_note_kind.returncode != 0,
    )

    edge_proj = "C:/fake/projectEdges"
    claim = ledger.append(edge_proj, "decision", text="tests pass")
    source_ref = "receipt:test-run-1"
    target_ref = f"seq:{claim['seq']}"
    try:
        supports = ledger.append_claim_edge(
            edge_proj,
            "supports",
            source=source_ref,
            target=target_ref,
        )
        contradicts = ledger.append_claim_edge(
            edge_proj,
            "contradicts",
            source=source_ref,
            target=target_ref,
        )
        matches = ledger.claim_edges(
            edge_proj,
            relation="supports",
            source=source_ref,
            target=target_ref,
        )
        stored = [
            json.loads(line)
            for line in ledger._events_file(edge_proj)
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        direct_ok = (
            supports.get("kind") == "claim_edge"
            and supports.get("seq") == claim["seq"] + 1
            and supports in stored
            and contradicts in stored
            and len(matches) == 1
            and matches[0].get("seq") == supports["seq"]
        )
    except Exception as ex:
        check(f"typed edges share and query events.jsonl (raised {ex})", False)
    else:
        # Known-broken before G-04: no edge API or claim_edge event kind exists.
        check("typed edges share and query events.jsonl", direct_ok)

    before_invalid = ledger.state(edge_proj)["seq"]
    direct_schema_rejected = False
    invalid_rejected = False
    empty_ref_rejected = False
    empty_target_rejected = False
    invalid_query_rejected = False
    try:
        ledger.append(
            edge_proj,
            "claim_edge",
            relation="supports",
            source=source_ref,
        )
    except ValueError:
        direct_schema_rejected = True
    except Exception:
        pass
    try:
        ledger.append_claim_edge(
            edge_proj,
            "invented_relation",
            source=source_ref,
            target=target_ref,
        )
    except ValueError:
        invalid_rejected = True
    except Exception:
        pass
    try:
        ledger.append_claim_edge(
            edge_proj,
            "supports",
            source=source_ref,
            target="",
        )
    except ValueError:
        empty_target_rejected = True
    except Exception:
        pass
    try:
        ledger.claim_edges(edge_proj, relation="invented_relation")
    except ValueError:
        invalid_query_rejected = True
    except Exception:
        pass
    try:
        ledger.append_claim_edge(
            edge_proj,
            "supports",
            source="",
            target=target_ref,
        )
    except ValueError:
        empty_ref_rejected = True
    except Exception:
        pass
    # Known-broken before G-04: no boundary rejects malformed edge writes/queries.
    check(
        "invalid edge schema is rejected without an append",
        direct_schema_rejected
        and invalid_rejected
        and empty_ref_rejected
        and empty_target_rejected
        and invalid_query_rejected
        and ledger.state(edge_proj)["seq"] == before_invalid,
    )

    failure = ledger.append(edge_proj, "failure", text="retired claim")
    note_result = subprocess.run(
        [
            sys.executable,
            str(HERE / "note.py"),
            "--kind",
            "milestone",
            "--cwd",
            edge_proj,
            "--supersedes",
            str(failure["seq"]),
            "replacement claim",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    try:
        milestone = next(
            event
            for event in reversed(ledger.replay(edge_proj, 20))
            if event.get("kind") == "milestone"
            and event.get("text") == "replacement claim"
        )
        supersedes = ledger.claim_edges(
            edge_proj,
            relation="supersedes",
            source=f"seq:{milestone['seq']}",
            target=f"seq:{failure['seq']}",
        )
        cli_edge_ok = (
            note_result.returncode == 0
            and len(supersedes) == 1
            and supersedes[0].get("kind") == "claim_edge"
            and all(
                item.get("seq") != failure["seq"]
                for item in ledger.state(edge_proj)["open_failures"]
            )
        )
    except Exception:
        cli_edge_ok = False
    # Known-broken before G-04: --supersedes tombstones but stores no claim_edge.
    check(
        "note --supersedes writes a typed edge and preserves tombstoning",
        cli_edge_ok,
    )

    print("== per-project isolation (slug) ==")
    ledger.append("C:/fake/projectB", "goal", text="other")
    check("projectA seq unaffected by projectB", ledger.state(proj)["seq"] == 4)
    check("projectB independent seq", ledger.state("C:/fake/projectB")["seq"] == 1)

    print("== bad field never raises ==")
    try:
        ledger.append(proj, "note", weird=object())
        check("non-serializable field tolerated", True)
    except Exception as ex:
        check(f"non-serializable field tolerated (raised {ex})", False)

    print("== stop-hook honors stop_hook_active (no write) ==")

    def run_hook(modfile, stdin_obj):
        spec = importlib.util.spec_from_file_location(modfile.stem, modfile)
        mod = importlib.util.module_from_spec(spec)
        old_stdin, old_stdout = sys.stdin, sys.stdout
        sys.stdin = io.StringIO(json.dumps(stdin_obj))
        cap = io.StringIO()
        sys.stdout = cap
        try:
            spec.loader.exec_module(mod)
            rc = mod.main()
        finally:
            sys.stdin, sys.stdout = old_stdin, old_stdout
        return rc, cap.getvalue()

    before = ledger.state(proj)["seq"]
    rc, _ = run_hook(HERE / "stop-hook.py", {"cwd": proj, "stop_hook_active": True})
    check("stop-hook exit 0 when active", rc == 0)
    check("stop-hook wrote nothing when active", ledger.state(proj)["seq"] == before)

    print("== sessionstart-replay emits additionalContext ==")
    rc, out = run_hook(
        HERE / "sessionstart-replay.py", {"cwd": proj, "source": "resume"}
    )
    ok_json = False
    try:
        payload = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
        ctx = payload.get("hookSpecificOutput", {}).get("additionalContext", "")
        ok_json = "Event ledger" in ctx and "ship the ledger" in ctx
    except Exception:
        ok_json = False
    check("replay injects ground-truth context", ok_json)

    print("== deferred open threads survive recovery ==")
    tproj = "C:/fake/projectThreads"
    open_cli = subprocess.run(
        [
            sys.executable,
            str(HERE / "note.py"),
            "--kind",
            "thread",
            "--cwd",
            tproj,
            "--id",
            "T-17",
            "revisit parser after dependency lands",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    # Known-broken before this fix: KINDS carried no "thread", so the CLI exited 2 and a
    # direct append silently downgraded the row to "note".
    check("thread is a first-class annotation kind", "thread" in ledger.KINDS)
    check("note CLI records a typed thread", open_cli.returncode == 0)
    ledger.append(tproj, "note", text="freeform aside worth keeping")
    check(
        "open_threads projects exactly the deferred item",
        [t.get("id") for t in (ledger.state(tproj).get("open_threads") or [])]
        == ["T-17"],
    )

    def replay_ctx(project):
        _, raw = run_hook(
            HERE / "sessionstart-replay.py", {"cwd": project, "source": "compact"}
        )
        try:
            return (
                json.loads(raw.strip().splitlines()[-1])
                .get("hookSpecificOutput", {})
                .get("additionalContext", "")
            )
        except Exception:
            return ""

    ctx_open = replay_ctx(tproj)
    # Known-broken before this fix: build_context replayed neither an open-thread
    # projection nor note rows, so a deferred item was dropped from recovery context
    # even though the injected header advertised "decisions/notes".
    check("recovery replays the open thread", "T-17" in ctx_open)
    check("recovery replays the note rows its header promises", "aside" in ctx_open)

    close_cli = subprocess.run(
        [
            sys.executable,
            str(HERE / "note.py"),
            "--kind",
            "thread",
            "--cwd",
            tproj,
            "--id",
            "T-17",
            "--status",
            "closed",
            "parser revisited",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    # A reconciled projection, not another memory source: closing retires the row instead
    # of appending a second one, so a settled item stops being replayed forever.
    check(
        "closing a thread retires it from the projection and from recovery",
        close_cli.returncode == 0
        and (ledger.state(tproj).get("open_threads") or []) == []
        and "T-17" not in replay_ctx(tproj),
    )

    print(
        f"\nRESULT: {'PASS' if not fails else 'FAIL: ' + ', '.join(fails)}  "
        f"({len(fails)} failures)"
    )
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
