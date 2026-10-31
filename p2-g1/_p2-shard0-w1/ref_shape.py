import json

doc = json.load(open('command-center/adversarial/ADV-0029-dependency-confusion-index-poisoning.json', encoding='utf-8'))
print('top keys:', sorted(doc.keys()))
print('schema_version:', doc.get('schema_version'))
print('artifacts[0]:', json.dumps((doc.get('artifacts') or [None])[0], indent=1))
ev = doc.get('evidence') or []
print('evidence count:', len(ev))
if ev:
    e0 = dict(ev[0])
    pr = e0.get('probes')
    if pr:
        e0['probes'] = ['<probe0>', '<probe1>']
    print('evidence[0] (probes elided):', json.dumps(e0, indent=1)[:1200])
    if pr:
        print('evidence[0].probes[0]:', json.dumps(pr[0], indent=1))
        print('evidence[0].probes[1]:', json.dumps(pr[1], indent=1))
