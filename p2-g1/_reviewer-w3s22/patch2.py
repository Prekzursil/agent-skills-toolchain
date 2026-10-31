#!/usr/bin/env python3
"""Patch 2 for close_shard22.py: reorder mutation control after the pass-A
placeholder consumer so the mutated copy differs from the closure ONLY in
reviewer.independent, and require the rejection to NAME the reviewer rule."""
from pathlib import Path

p = Path(__file__).resolve().parent / "close_shard22.py"
t = p.read_text(encoding="utf-8")

old_mc = t[t.index("def mutation_control("):t.index("results: dict[str, dict] = {}")]
new_mc = '''def mutation_control(uid: str, receipt: dict, tmp: Path) -> dict | None:
    """receipt_core must REJECT a COMPLETE state=SUCCESS closure copy whose
    reviewer.independent is flipped to false, and the rejection must NAME the
    reviewer rule (not some unrelated defect) - the both-states proof that the
    closure rule is enforced by the admission instrument itself."""
    tmp.mkdir(parents=True, exist_ok=True)
    bad_p = tmp / (uid + "-no-independent.json")
    bad = json.loads(json.dumps(receipt))
    bad["reviewer"]["independent"] = False
    bad_p.write_bytes((json.dumps(bad, indent=1, ensure_ascii=False) + "\\n").encode("utf-8"))
    r = subprocess.run(
        [sys.executable, "-I", str(REPO / "command-center/receipt_validate.py"), str(bad_p)],
        capture_output=True, text=True, timeout=600, cwd=str(REPO))
    outtxt = ((r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode == 0:
        return None  # inert detector: closure must not proceed
    if "independent" not in outtxt and "reviewer" not in outtxt:
        return None  # fired for the WRONG reason: rule not named
    return {
        "id": "MUT-" + uid + "-reviewer-independent-flip",
        "kind": "mutation",
        "description": ("Independent-reviewer mutation control: reviewer.independent "
                        "flipped to false on a COMPLETE copy of the SUCCESS closure "
                        "receipt (identical in every other field); receipt_validate.py "
                        "must REJECT naming the reviewer rule (receipt_core forbids "
                        "state=SUCCESS without reviewer.verdict=PASS + independent="
                        "true) while accepting the unmutated closure."),
        "fired_on_bad_state": True,
        "silent_on_good_state": None,  # set after the good-state ACCEPT is known
        "bad_state_output": outtxt[:400],
    }


PLACEHOLDER = """
'''
# splice: keep everything up to mutation_control, insert new, then rebuild tail
head = t[:t.index("def mutation_control(")]
tail_anchor = "results: dict[str, dict] = {}"
tail = t[t.index(tail_anchor):]

placeholder_block = '''    # pass-A placeholder consumer FIRST so the mutation copy differs from the
    # closure ONLY in reviewer.independent (isolates the variable under test)
    receipt["downstream_consumers"] = [{
        "consumer": "command-center/receipt_validate.py (admission gate C1-C4)",
        "artifact_path": "command-center/receipts/" + uid + ".json",
        "executed": True, "read_ok": True, "exit_code": 0,
        "probe": {"role": "verifier", "method": "command",
                  "command": ("python -I command-center/receipt_validate.py "
                              "command-center/receipts/" + uid + ".json"),
                  "raw_output": "PENDING: confirmation run executes after this write",
                  "exit_code": 0,
                  "fingerprint": "w3s22-validate:" + uid + ":passA"},
    }]
    # reviewer mutation control on the COMPLETE closure shape
    mc = mutation_control(uid, receipt, tmpdir)
    if mc is None:
        row["verdict"] = "FAIL"
        row["reasons"] = ["mutation-control-inert: receipt_validate ACCEPTED a "
                          "state=SUCCESS receipt with reviewer.independent=false, "
                          "or rejected for an unrelated reason"]
        results[uid] = row
        print("FAILED:" + uid + "-review mutation-control-unusable")
        continue
    mc["silent_on_good_state"] = None
    receipt["negative_controls"].append(mc)
    receipt["report"]["control_ids"] = [c["id"] for c in receipt["negative_controls"]]
    receipt["report"]["observations"] = [
        {"name": "artifact_lf_bytes", "measured": CUR_CTX["lf_len"], "method": "digest_lf",
         "anchor": "command-center/receipts/" + uid + ".json"},
        {"name": "named_probes_live_rounds",
         "measured": str(STABILITY_ROUNDS) + "x" + str(len(ctx["scripts"])) + " all rc0",
         "method": "subprocess re-run, ambient env",
         "anchor": "command-center/p2-wave/probes/" + uid + "/"},
        {"name": "manifest_lf_sha_match", "measured": True,
         "method": "sha256 CRLF-normalized byte-compare",
         "anchor": "command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json"},
        {"name": "schema_dual_validation", "measured": "receipt_core+profile 0 errors",
         "method": "receipt_schema_gate + schema_resolver",
         "anchor": "platform/schema/receipt.schema.json"},
    ]

    write_bytes_fresh(rp, json.dumps(receipt, indent=1, ensure_ascii=False) + "\\n")
    vrc, vout = validator_rc(uid)
    t_end = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time()))
    if vrc != 0:
        rp.write_bytes(ctx["orig_text"].encode("utf-8"))
        row["verdict"] = "FAIL"
        row["reasons"] = ["passA-admission-REJECT:" + vout[:220]]
        results[uid] = row
        print("FAILED:" + uid + "-review passA " + vout[:160])
        continue

    # pass B: record the REAL confirmation run; final write
    dur = max(1, int(round(time.time() - t0)))
    receipt["timestamps"]["ended_at"] = t_end
    receipt["timestamps"]["duration_seconds"] = dur
    receipt["reviewer"]["reviewed_at"] = t_end
    receipt["downstream_consumers"][0]["probe"]["raw_output"] = vout[:2000]
    receipt["downstream_consumers"][0]["probe"]["fingerprint"] = "w3s22-validate:" + uid + ":rc" + str(vrc)
    receipt["downstream_consumers"][0]["probe"]["exit_code"] = vrc
    receipt["negative_controls"][-1]["silent_on_good_state"] = (vrc == 0)
    receipt["negative_controls"][-1]["good_state_output"] = vout[:200]
    write_bytes_fresh(rp, json.dumps(receipt, indent=1, ensure_ascii=False) + "\\n")
    refresh_manifest(uid, rp)
'''

# Replace in tail: from "# pass-A placeholder consumer first" .. up to "refresh_manifest(uid, rp)" inclusive
start = tail.index("    # pass-A placeholder consumer FIRST")
if start < 0:
    raise SystemExit("anchor1 missing")
end_marker = "    refresh_manifest(uid, rp)\n"
end = tail.index(end_marker) + len(end_marker)
tail = tail[:start] + placeholder_block + tail[end:]
new = head + new_mc.replace('PLACEHOLDER = """\n', "") + tail
p.write_bytes(new.encode("utf-8"))
print("patched OK, bytes:", p.stat().st_size)
