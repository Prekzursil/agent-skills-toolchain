import json, os
repo = r'C:\Users\Prekzursil\p2-g1'
ids = ['IMP-0261','IMP-0264','IMP-0269','IMP-0270','IMP-0271','IMP-0272','IMP-0273','IMP-0274','IMP-0275','IMP-0279','IMP-0303','IMP-0304']
for uid in ids:
    p = os.path.join(repo,'command-center','receipts',uid+'.json')
    d = json.load(open(p, encoding='utf-8'))
    rv = d.get('reviewer') or {}
    pb = d.get('produced_by') or {}
    print(uid)
    print('   builder:', pb.get('vendor'), pb.get('model'), pb.get('role'), '| substrate:', pb.get('execution_substrate'))
    print('   reviewer:', rv.get('reviewer_id'), '| vendor:', rv.get('vendor'), '| verdict:', rv.get('verdict'),
          '| independent:', rv.get('independent'), '| fresh:', rv.get('fresh_context'), '| starts_from:', rv.get('starts_from') or rv.get('starts_from_tests') or rv.get('started_from'))
    print('   state:', d.get('state'), '| reviewer_verdict field:', d.get('reviewer_verdict'))
