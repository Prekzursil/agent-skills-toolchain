import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r'C:/Users/Prekzursil/p2-g1')
MINE = ["AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057",
        "AUD-0064", "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072",
        "AUD-0075", "AUD-0080"]

OUT = {}
only = sys.argv[1:] if len(sys.argv) > 1 else MINE
for uid in only:
    pd = REPO / f'command-center/p2-wave/probes/{uid}'
    ret = json.loads((pd / 'SUBAGENT-RETURN.json').read_text(encoding='utf-8'))
    cmds = []
    for item in (ret.get('named_probes') or []):
        if isinstance(item, dict) and isinstance(item.get('command'), str):
            cmds.append(item['command'].strip())
    if len(cmds) < 2:
        p1 = sorted(pd.glob('probe1*.py'))
        p2 = sorted(pd.glob('probe2*.py'))
        a = p1[0] if p1 else None
        b = p2[0] if p2 else None
        cmds = [f'PYTHONDONTWRITEBYTECODE=1 python3 -B {x.relative_to(REPO).as_posix()}' for x in (a, b) if x]
    rows = []
    for cmd in cmds:
        m = re.match(r'^PYTHONDONTWRITEBYTECODE=1\s+python3?\s+-B\s+(\S+)$', cmd)
        if not m:
            rows.append({'cmd': cmd, 'rc': None, 'error': 'unparsed-command-form'})
            continue
        script = REPO / m.group(1).replace('/', '\\')
        if not script.exists():
            rows.append({'cmd': cmd, 'rc': None, 'error': 'script-missing'})
            continue
        try:
            p = subprocess.run([sys.executable, '-B', str(script)], cwd=str(REPO),
                               capture_output=True, text=True, timeout=300)
            out = (p.stdout or '') + (p.stderr or '')
            pass_flags = re.findall(r'"pass":\s*(true|false)', out)
            rows.append({'cmd': cmd, 'rc': p.returncode,
                         'pass_flags': pass_flags,
                         'tail': out[-300:] if p.returncode != 0 else out[-160:]})
        except subprocess.TimeoutExpired:
            rows.append({'cmd': cmd, 'rc': None, 'error': 'timeout-300s'})
        except Exception as e:
            rows.append({'cmd': cmd, 'rc': None, 'error': f'{type(e).__name__}: {str(e)[:120]}'})
    ok = all(r.get('rc') == 0 for r in rows) and len(rows) >= 2
    OUT[uid] = {'probes_ok': ok, 'rows': rows}
    print(f"{uid}: probes_ok={ok}")
    for r in rows:
        print(f"   rc={r.get('rc')} {r.get('error') or ''} pass_flags={r.get('pass_flags')}")
Path(__file__).parent.joinpath('probe-results.json').write_text(json.dumps(OUT, indent=1), encoding='utf-8')
print('ALL-PROBES-OK' if all(v['probes_ok'] for v in OUT.values()) else 'SOME-PROBES-FAILED')
