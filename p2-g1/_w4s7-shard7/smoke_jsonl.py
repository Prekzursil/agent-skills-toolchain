import sys, tempfile, json
sys.path.insert(0, 'tools')
from pathlib import Path
from plugin.jsonl_log import JsonlLogger

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / 'log' / 'events.log'
    lg = JsonlLogger(p, 'SMOKE', max_bytes=400, max_files=3)
    secret = 'ghp_' + 'AbCdEf1234567890' * 2
    for i in range(60):
        lg.write('OK', i=i, note=f'filler {i} ' + 'x' * 20, token=secret)
    files = lg.all_files()
    sizes = [f.stat().st_size for f in files]
    allbytes = b''.join(f.read_bytes() for f in files)
    ok_size = all(s <= 400 for s in sizes)
    ok_count = len(files) <= 3
    secret_gone = secret.encode() not in allbytes
    redacted = allbytes.count(b'[REDACTED]')
    lines = [l for l in allbytes.split(b'\n') if l.strip()]
    parse_ok = True
    newest_i = None
    try:
        for l in lines:
            json.loads(l)
        newest_i = json.loads(lines[-1])['fields'].get('i')
    except Exception as exc:
        parse_ok = False
        print('PARSE FAIL', exc)
    print('files:', len(files), 'sizes<=400:', ok_size, 'count<=3:', ok_count)
    print('secret-gone:', secret_gone, 'redacted-count:', redacted)
    print('all-lines-parse:', parse_ok, 'newest-i:', newest_i)
