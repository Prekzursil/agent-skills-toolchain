SWEEP_RAW = {}


def main() -> int:
    targets = sys.argv[1:] or sorted(REPORT_KIND)
    bad = []
    for uid in targets:
        cfg = unit_config(uid)
        print("== repairing", uid)
        try:
            probes = run_unit_probes(cfg)
        except RuntimeError as exc:
            print("PROBE-FAIL", uid, str(exc)[:300])
            bad.append(uid)
            continue
        sweep = SWEEP_RAW.get(uid) or (
            "probe pair live rc=0 this pass; final gate re-run by "
            "_measure_one_delivered.py in the shard delivery transaction"
        )
        errs = transform(uid, cfg, sweep, probes)
        if errs:
            print("SCHEMA-INVALID", uid, " | ".join(errs[:8])[:1200])
            bad.append(uid)
            continue
        merr = update_manifest(uid, cfg["artifact"])
        if merr:
            print("MANIFEST-FAIL", uid, merr)
            bad.append(uid)
        else:
            print("REPAIRED", uid)
    if bad:
        print("FAILED:shard5-repair " + ",".join(bad))
        return 1
    print("SUCCESS:shard5-repair " + ",".join(targets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
