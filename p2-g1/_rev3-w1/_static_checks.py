import sys, os, json, io
sys.path.insert(0, r'C:/Users/Prekzursil/p2-g1/_rev3-w1')
from _util import load_json, sha256_lf, repo, UNITS

cat = load_json(repo('command-center','WORK-UNIT-CATALOG.json'))
by_id = {u['id']: u for u in cat['work_units']}

for uid in UNITS:
    print('='*100)
    u = by_id[uid]
    out_rel = u['output_path']
    art = repo(*out_rel.split('/'))
    print(f"[{uid}] output_path: {out_rel}")
    if not os.path.isfile(art):
        print(f"  FAIL artifact missing"); continue
    size = os.path.getsize(art)
    print(f"  exists size={size}", end='')
    if size <= 0:
        print(" FAIL empty"); continue
    try:
        doc = load_json(art)
        print(" | parses OK", end='')
    except Exception as e:
        print(f" FAIL parse: {e}"); continue
    live_sha = sha256_lf(art)
    man_rel = f'command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json'
    man = load_json(repo(*man_rel.split('/')))
    rows = [a for a in man.get('artifacts', []) if a.get('path') == out_rel]
    if not rows:
        print(f" | FAIL no manifest row for output_path")
    else:
        for r in rows:
            match = (r.get('sha256') == live_sha)
            bmatch = (r.get('bytes') == size)
            print(f" | manifest row role={r.get('role')} sha_match={match} bytes_match={bmatch} (live={live_sha[:12]} man={str(r.get('sha256'))[:12]})")
    # state fields
    st = doc.get('state')
    sent = str(doc.get('sentinel') or '')
    comp = str(doc.get('completion_line') or '')
    marker = str(doc.get('completion_marker') or '')
    print(f"  state={st!r}")
    print(f"  sentinel[:110]={sent[:110]!r}")
    print(f"  completion_line={comp!r} marker={marker[:40]!r}")
    selfdecl = st in {'BLOCKED','FAILED','SEVERED','TIMEOUT'}
    sent_bad = sent.startswith('FAILED:') or sent.startswith('BLOCKED:')
    print(f"  selfdecl_state={selfdecl} sentinel_declares_fail={sent_bad}")
    # schema validation with jsonschema, resolving absolute $refs
    import jsonschema
    from jsonschema import Draft202012Validator
    schema_rel = u['output_schema']
    schema = load_json(repo(*schema_rel.split('/')))
    try:
        # use referencing library via jsonschema; absolute file:// refs to source/ast-integrate
        v = Draft202012Validator(schema)
        errs = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
        if errs:
            print(f"  SCHEMA: {len(errs)} errors; first 5:")
            for e in errs[:5]:
                print(f"    - path={list(e.path)[:8]}: {str(e.message)[:160]}")
        else:
            print(f"  SCHEMA: VALID ({schema_rel})")
    except Exception as e:
        print(f"  SCHEMA: validator error: {type(e).__name__}: {str(e)[:200]}")
