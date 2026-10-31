import json
import subprocess
import sys
import time

REPO = r'C:/Users/Prekzursil/p2-g1'
MEASURE = REPO + '/command-center/p2-wave/_measure_one_delivered.py'
UNITS = ["IMP-0084", "IMP-0090", "IMP-0093", "IMP-0097", "IMP-0098", "IMP-0103",
         "IMP-0134", "IMP-0147", "IMP-0154", "IMP-0165", "IMP-0168", "IMP-0189"]
LOG = REPO + '/_reviewer_w3s10_probe_battery.log'

py = sys.executable
with open(LOG, 'w', encoding='utf-8') as log:
    log.write('START %s\n' % time.strftime('%Y-%m-%dT%H:%M:%S'))
    for uid in UNITS:
        t0 = time.time()
        try:
            p = subprocess.run(
                [py, '-I', '-B', MEASURE, uid],
                cwd=REPO, capture_output=True, text=True, timeout=2900)
            rc = p.returncode
            out = ((p.stdout or '') + (p.stderr or ''))[-600:]
        except subprocess.TimeoutExpired:
            rc, out = 124, 'TIMEOUT after 2900s'
        line = '%s rc=%d %.1fs | %s' % (uid, rc, time.time() - t0, out.replace('\n', ' | ')[:400])
        print(line, flush=True)
        log.write(line + '\n')
        log.flush()
    log.write('DONE %s\n' % time.strftime('%Y-%m-%dT%H:%M:%S'))
