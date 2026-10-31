import hashlib
import json
import sys
from pathlib import Path

import jsonschema

REPO = Path(r'C:/Users/Prekzursil/p2-g1')
MINE = ["AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057",
        "AUD-0064", "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072",
        "AUD-0075", "AUD-0080"]
BLOCK_STATES = {'BLOCKED', 'FAILED', 'SEVERED', 'TIMEOUT'}


def digest_live(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def self_blocked(doc) -> list:
    """Any state/status/verdict field self-declaring BLOCKED/FAILED/SEVERED/TIMEOUT."""
    hits = []
    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ('state', 'status', 'verdict') and isinstance(v, str) and v.upper() in BLOCK_STATES:
                    hits.append(f'{path}.{k}={v}')
                else:
                    walk(v, f'{path}.{k}')
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f'{path}[{i}]')
    walk(doc, '$')
    return hits


def schema_validate(art_path: Path, schema_path: Path):
    try:
        schema = json.loads(schema_path.read_text(encoding='utf-8'))
    except Exception as e:
        return False, f'schema-unreadable: {e}'
    try:
        doc = json.loads(art_path.read_text(encoding='utf-8'))
    except Exception as e:
        return False, f'artifact-unreadable: {e}'
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        v = jsonschema.Draft202012Validator(schema)
        errs = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
        if errs:
            msgs = [f"{list(e.path)}: {e.message[:160]}" for e in errs[:8]]
            return False, f'{len(errs)} errors; first: {msgs[0]}'
        return True, 'valid'
    except Exception as e:
        return False, f'validator-error: {type(e).__name__}: {str(e)[:150]}'


def main() -> int:
    cat = json.loads((REPO / 'command-center/WORK-UNIT-CATALOG.json').read_text(encoding='utf-8'))
    byid = {e['id']: e for e in cat['work_units']}
    results = {}
    all_ok = True
    for uid in MINE:
        e = byid[uid]
        rec = {'checks': {}}
        ok = True
        out_rel = str(e['output_path']).replace('\\', '/')
        out_path = REPO / out_rel
        # 1. artifact exists / non-empty / parses / not self-blocked
        if not out_path.exists():
            rec['checks']['artifact'] = 'MISSING'
            ok = False
        else:
            size = out_path.stat().st_size
            rec['artifact_bytes'] = size
            if size == 0:
                rec['checks']['artifact'] = 'EMPTY'
                ok = False
            else:
                try:
                    art = json.loads(out_path.read_text(encoding='utf-8'))
                    sb = self_blocked(art)
                    rec['checks']['artifact'] = 'ok' if not sb else f'SELF-BLOCKED {sb[:3]}'
                    if sb:
                        ok = False
                except Exception as ex:
                    rec['checks']['artifact'] = f'PARSE-FAIL {str(ex)[:120]}'
                    ok = False
                    art = None
        # 2. manifest primary row sha match
        man_p = REPO / f'command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json'
        try:
            man = json.loads(man_p.read_text(encoding='utf-8'))
            rows = [a for a in man.get('artifacts', [])
                    if str(a.get('path', '')).replace('\\', '/') == out_rel and a.get('role') == 'primary']
            if out_path.exists():
                live = digest_live(out_path)
                rec['live_sha256'] = live
                if not rows:
                    rec['checks']['manifest_sha'] = 'NO-PRIMARY-ROW'
                    ok = False
                else:
                    row = rows[0]
                    mism = []
                    if row.get('sha256') != live:
                        mism.append(f"sha manifest={row.get('sha256','')[:12]} live={live[:12]}")
                    if row.get('present') is not True:
                        mism.append('present!=true')
                    if row.get('bytes') != out_path.stat().st_size:
                        mism.append(f"bytes manifest={row.get('bytes')} live={out_path.stat().st_size}")
                    rec['checks']['manifest_sha'] = 'ok' if not mism else '; '.join(mism)
                    if mism:
                        ok = False
            else:
                rec['checks']['manifest_sha'] = 'skipped(no artifact)'
        except Exception as ex:
            rec['checks']['manifest_sha'] = f'MANIFEST-ERROR {str(ex)[:120]}'
            ok = False
        # 3. receipt artifacts row sha match
        rp = REPO / f'command-center/receipts/{uid}.json'
        try:
            rdoc = json.loads(rp.read_text(encoding='utf-8'))
            rrows = [a for a in (rdoc.get('artifacts') or [])
                     if str(a.get('path', '')).replace('\\', '/') == out_rel]
            if out_path.exists() and rrows:
                live = rec.get('live_sha256') or digest_live(out_path)
                if rrows[0].get('sha256') == live:
                    rec['checks']['receipt_artifact_sha'] = 'ok'
                else:
                    rec['checks']['receipt_artifact_sha'] = f"receipt-row sha={str(rrows[0].get('sha256'))[:12]} != live"
                    ok = False
            elif not rrows:
                rec['checks']['receipt_artifact_sha'] = 'NO-RECEIPT-ROW'
                ok = False
            else:
                rec['checks']['receipt_artifact_sha'] = 'skipped(no artifact)'
        except Exception as ex:
            rec['checks']['receipt_artifact_sha'] = f'RECEIPT-ERROR {str(ex)[:120]}'
            ok = False
        # 4. output_schema validation
        sch_rel = str(e.get('output_schema', '')).replace('\\', '/')
        if sch_rel and out_path.exists():
            vok, vmsg = schema_validate(out_path, REPO / sch_rel)
            rec['checks']['output_schema'] = vmsg if vok else f'FAIL {vmsg}'
            if not vok:
                ok = False
        else:
            rec['checks']['output_schema'] = 'NO-SCHEMA-DECLARED'
        # 5. SUBAGENT-RETURN state
        srp = REPO / f'command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json'
        try:
            sr = json.loads(srp.read_text(encoding='utf-8'))
            st = sr.get('state', '?')
            rec['checks']['subagent_return'] = st if st in BLOCK_STATES else 'ok'
            if st in BLOCK_STATES:
                ok = False
        except Exception as ex:
            rec['checks']['subagent_return'] = f'UNREADABLE {str(ex)[:100]}'
            ok = False
        # 6. receipt state/reviewer snapshot
        try:
            rdoc = json.loads(rp.read_text(encoding='utf-8'))
            rev = rdoc.get('reviewer') or {}
            rec['receipt'] = {
                'state': rdoc.get('state'),
                'verdict': rev.get('verdict'),
                'independent': rev.get('independent'),
                'reviewer_id': rev.get('reviewer_id'),
            }
        except Exception as ex:
            rec['receipt'] = f'UNREADABLE {str(ex)[:100]}'
            ok = False
        rec['static_ok'] = ok
        all_ok &= ok
        results[uid] = rec
    outp = Path(__file__).parent / 'static-results.json'
    outp.write_text(json.dumps(results, indent=1), encoding='utf-8')
    for uid, r in results.items():
        flags = '; '.join(f'{k}={v}' for k, v in r['checks'].items() if v != 'ok')
        print(f"{uid}: static_ok={r['static_ok']}{' | ' + flags if flags else ''}")
    print('ALL-STATIC-OK' if all_ok else 'SOME-STATIC-FAILED')
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
