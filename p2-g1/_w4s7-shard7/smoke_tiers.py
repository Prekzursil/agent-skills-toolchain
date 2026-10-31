import sys
sys.path.insert(0, 'tools')
from marketplace.trust_tiers import assign_tier, decide_admission, AUTO_ADMIT, REFUSED, CONDITIONAL

FP = {'publisher_id': 'prekzursil', 'publisher_repo': 'Prekzursil/ast-integrate', 'identity_verified': True, 'signature_verified': True}
first_party = {'trust_evidence': FP}
vendor = {'trust_evidence': {'publisher_id': 'acme', 'publisher_repo': 'acme/widgets', 'identity_verified': True, 'signature_verified': True}}
community = {'trust_evidence': {'preview_url': 'http://x', 'publisher_id': 'dev42', 'publisher_repo': 'dev42/w', 'identity_verified': True, 'signature_verified': False}}
unknown = {'trust_evidence': {'publisher_id': 'stranger', 'publisher_repo': '', 'identity_verified': False, 'tier_hint': 'first-party'}}
r = []
for name, c in [('first-party', first_party), ('vendor', vendor), ('community', community), ('unknown', unknown)]:
    a = assign_tier(c)
    d = decide_admission(c)
    r.append((name, a.tier, d.verdict))
    print(name, '->', a.tier, '|', d.verdict)
assert [x[1] for x in r] == ['first-party', 'vendor', 'community', 'unknown']
assert d.verdict == REFUSED
twin_fp = dict(unknown)
twin_fp['trust_evidence'] = dict(FP)
assert decide_admission(twin_fp).verdict == AUTO_ADMIT
u2 = {'trust_evidence': {**unknown['trust_evidence'], 'owner_approval': True}}
assert decide_admission(u2).verdict == CONDITIONAL
print('TIERS SMOKE OK')
