import hashlib, os
root = os.path.join(os.path.expanduser("~"), "p2-g1")
expect = [
 ("IMP-0165", "tools/workflow_foundry/role_extract.py", "2febeb7b66b024087b51a4a24a806ec74b61514ef0addb11ff86c086e59fe399", 5707),
 ("IMP-0219", "tools/agentspec/agentspec/fanout.py", "8e11f5104775f63cc0340043bd0198bddcf0ed91ac662edadda153984a00935b", 3890),
 ("IMP-0219", "tools/agentspec/agentspec/oracle.py", "da2c0cc9bc0b1393b2e2f8feda42ae6c875faafe5b8cd4089bad2cbfa08b9816", 13977),
 ("IMP-0219", "tools/agentspec/agentspec/progress.py", "2fc566e0a8039a44ac3c3ab18578d79f03f4c34a2d0231f07dbd31b552a57804", 4523),
 ("IMP-0224", "tools/event-ledger/ledger.py", "331613d46f0ab39f25b7d5f1bdaf2a086e9ead88d9af701913f96e37e072f5a8", 18021),
 ("IMP-0224", "tools/event-ledger/kill_target.py", "13558230653e4e4b44717b0836b9a604bee99e78066b2752de3e7090fd49a2c8", 2335),
 ("IMP-0224", "tools/event-ledger/schema/record.schema.json", "adaafa2ca8a1fb8bfe17dbbff2442eff71e080a85ecb4c73631253fc67180d2f", 1530),
 ("IMP-0224", "tools/event-ledger/tests/test_crash_safe.py", "a951f8d52da72c611887fda916ec4423c53c03aa56db1592e8f5fd797406ca29", 5446),
 ("IMP-0224", "tools/lib/handled-ledger.mjs", "830a17edcc18866310e22f3f87f893e5c85d169b16c6cf253570b8909ab768cd", 5799),
]
for uid, rel, sha, nb in expect:
    p = os.path.join(root, rel.replace("/", "\\"))
    if not os.path.isfile(p):
        print(uid, rel, "MISSING")
        continue
    raw = open(p, "rb").read()
    live = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    print(uid, rel, "OK" if live == sha else "SHA-DRIFT live=" + live[:12] + " bytes=%d" % len(raw))
