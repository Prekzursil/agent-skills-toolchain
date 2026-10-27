import hashlib, json, os, subprocess, sys, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent
PROBES = REPO / "command-center" / "p2-wave" / "probes"


def digest(p):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def row(path_rel, role, unit_id):
    p = REPO / path_rel
    sha, n = digest(p)
    return {
        "bytes": n,
        "path": path_rel.replace("\\", "/"),
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json" % unit_id,
        "role": role,
        "sha256": sha,
        "unit_id": unit_id,
    }


UNITS = json.loads(Path(__file__).with_name("_w4shard6_gen_units.json").read_text(encoding="utf-8"))
ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
for uid, spec in UNITS.items():
    udir = PROBES / uid
    artifacts_rows = []
    named_probes = []
    for pid, cmd, role, stem in spec["cmds"]:
        # Windows cmd.exe cannot run POSIX "VAR=value command" prefixes; move
        # them into the child env exactly like _measure_one_delivered.run_cmd.
        env_prefixes = {}
        c = cmd
        import re as _re
        while True:
            m = _re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", c)
            if m is None:
                break
            env_prefixes[m.group(1)] = m.group(2).strip(chr(34)).strip(chr(39))
            c = c[m.end():]
        p = subprocess.run(c, cwd=str(REPO), shell=True, capture_output=True,
                           text=True, timeout=900,
                           env=dict(os.environ, **env_prefixes))
        raw = (p.stdout or "") + (p.stderr or "")
        if p.returncode != 0:
            print("FAILED %s %s rc=%d\n%s" % (uid, pid, p.returncode, raw[-2000:]))
            sys.exit(1)
        (udir / (stem + ".raw.txt")).write_text(raw, encoding="utf-8", newline="\n")
        named_probes.append({
            "command": cmd,
            "exit_code": p.returncode,
            "id": pid,
            "raw_output_file": "command-center/p2-wave/probes/%s/%s.raw.txt" % (uid, stem),
            "raw_output_tail": raw.strip()[-700:],
            "role": role,
        })
        artifacts_rows.append(row("command-center/p2-wave/probes/%s/%s.py" % (uid, stem), "probe", uid))
    primary = row("command-center/receipts/%s.json" % uid, "primary", uid)
    artifacts_rows.append(primary)
    artifacts_rows.sort(key=lambda r: (0 if r["role"] == "primary" else 1, r["path"]))
    receipt = json.loads((REPO / "command-center" / "receipts" / (uid + ".json")).read_text(encoding="utf-8"))
    rv = receipt.get("reviewer", {})
    ret = {
        "artifacts": [primary],
        "id": uid,
        "named_probes": named_probes,
        "notes": spec["notes"],
        "output_path": receipt.get("output_path") or ("command-center/receipts/%s.json" % uid),
        "output_schema": receipt.get("output_schema"),
        "reviewer": {
            "kept_from_receipt": True,
            "independent": rv.get("independent"),
            "note": "prior independent closure; re-verified live by the rebuilt probe battery",
            "reviewer_id": rv.get("reviewer_id"),
            "verdict": rv.get("verdict"),
        },
        "sentinel": receipt.get("sentinel") or ("SUCCESS:" + uid),
        "status": "DELIVERED",
        "unit_id": uid,
        "verified_on_disk": ts,
    }
    (udir / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    manifest = {
        "artifacts": artifacts_rows + [row(rel, "supporting", uid) for rel in spec["supporting"]],
        "contract": "CRLF-normalized sha256 per _measure_one_delivered.digest_file",
        "derivation": "shard6-wave4-resume finalize (live re-run hashes)",
        "schema_version": 1,
        "unit_id": uid,
        "verified_on_disk": ts,
    }
    (udir / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("OK %s: primary sha=%s bytes=%d rows=%d" % (uid, primary["sha256"][:16], primary["bytes"], len(manifest["artifacts"])))
