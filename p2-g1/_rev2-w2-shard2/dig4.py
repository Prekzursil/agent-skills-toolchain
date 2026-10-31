import json
REPO = r'C:/Users/Prekzursil/p2-g1'
d = json.load(open(REPO + '/command-center/adversarial/ADV-0128-offline-and-partition-degrade-loudly.json', encoding='utf-8'))
print('verdict:', d.get('verdict'))
print('target_verdicts:', json.dumps(d.get('target_verdicts'))[:600])
print('detector_live:', json.dumps(d.get('detector_live'))[:300])
print('p1_finding:', json.dumps(d.get('p1_finding'))[:300])
oc = d.get('offline_campaign'); pc = d.get('partition_campaign')
print('offline_campaign:', json.dumps(oc)[:500])
print('partition_campaign:', json.dumps(pc)[:500])
print('cases:', len(d.get('cases', [])))
for c in d.get('cases', [])[:6]:
    print('  case:', json.dumps(c)[:220])
