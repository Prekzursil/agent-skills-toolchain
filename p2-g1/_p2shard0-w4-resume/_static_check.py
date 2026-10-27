import json, hashlib
from pathlib import Path
BS = chr(92)  # backslash, kept out of literals (MSYS mangling)
FS = chr(47)
REPO = Path.home() / 'p2-g1'
NOT_DELIVERING = {'BLOCKED','FAILED','SEVERED','TIMEOUT'}
cat = json.load(open(REPO/'command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
wu = {x['id']: x for x in cat['work_units']}
units = ['ADV-0038','ADV-0040','ADV-0090','ADV-0091','ADV-0096','ADV-0100','ADV-0109','ADV-0110','ADV-0117','ADV-0119','ADV-0123','ADV-0124']
def digest(p):
    raw = Path(p).read_bytes().replace(b'\r' + b'\n', b'\n')
    return hashlib.sha256(raw).hexdigest(), len(raw)
def norm(p):
    return str(p).replace(BS, FS)
summary = {}
for uid in units:
    u = wu[uid]
    out_rel = norm(u['output_path'])
    row = {'output_path': out_rel}
    out = REPO / out_rel
    row['artifact_exists'] = out.is_file()
    if out.is_file():
        try:
            text = out.read_text(encoding='utf-8')
            doc = json.loads(text)
            row['parses'] = True
            row['state'] = str(doc.get('state','')).upper()
            row['self_blocked'] = row['state'] in NOT_DELIVERING
            row['sentinel_present'] = (u.get('completion_sentinel') or '') in text
            row['bytes'] = out.stat().st_size
        except Exception as e:
            row['parses'] = False; row['parse_err'] = type(e).__name__
    else:
        row['parses'] = False
    ret_p = REPO/'command-center/p2-wave/probes'/uid/'SUBAGENT-RETURN.json'
    man_p = REPO/'command-center/p2-wave/probes'/uid/'UNIT-ARTIFACT-MANIFEST.json'
    row['receipt_exists'] = ret_p.is_file()
    if ret_p.is_file():
        try:
            ret = json.loads(ret_p.read_text(encoding='utf-8'))
            row['ret_status'] = ret.get('status')
            row['ret_state'] = ret.get('state')
            row['ret_reviewer'] = ret.get('reviewer')
            row['n_named_probes'] = len(ret.get('named_probes') or [])
        except Exception:
            row['ret_status'] = 'UNPARSEABLE'
    row['manifest_exists'] = man_p.is_file()
    if man_p.is_file() and out.is_file():
        try:
            man = json.loads(man_p.read_text(encoding='utf-8'))
            rows_m = [a for a in (man.get('artifacts') or []) if isinstance(a,dict) and a.get('unit_id')==uid]
            live_sha, _ = digest(out)
            match = [a for a in rows_m if norm(a.get('path') or '')==out_rel and str(a.get('sha256') or '')==live_sha and a.get('present') is True]
            row['manifest_rows'] = len(rows_m)
            row['sha_match'] = bool(match)
            row['live_sha12'] = live_sha[:12]
        except Exception:
            row['manifest_rows'] = 'ERR'
    summary[uid] = row
out_json = REPO/'_p2shard0-w4-resume/_static_check.json'
out_json.write_text(json.dumps(summary, indent=1), encoding='utf-8')
for uid, r in summary.items():
    verdict_bits = []
    if r.get('self_blocked'): verdict_bits.append('ARTIFACT-SELF-BLOCKED')
    if not r.get('parses'): verdict_bits.append('NO-PARSE')
    if not r.get('sentinel_present', False): verdict_bits.append('SENTINEL-ABSENT')
    if not r.get('sha_match', False): verdict_bits.append('SHA-MISMATCH')
    if r.get('ret_status') != 'DELIVERED': verdict_bits.append('RECEIPT-STATUS=' + str(r.get('ret_status')))
    print(uid, 'STATIC-OK' if not verdict_bits else ' | '.join(verdict_bits))
