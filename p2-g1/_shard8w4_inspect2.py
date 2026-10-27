import json, os
REPO = "C:/Users/Prekzursil/p2-g1"
for uid in ["IMP-0170", "IMP-0174", "IMP-0199", "IMP-0201", "IMP-0206"]:
    r = json.load(open(REPO + "/command-center/receipts/" + uid + ".json", encoding="utf-8"))
    print("=" * 30, uid)
    impl = r.get("implementation", {})
    print("impl keys:", sorted(impl.keys()) if isinstance(impl, dict) else type(impl).__name__)
    tests = r.get("tests", [])
    for t in tests:
        if isinstance(t, dict):
            print("test:", t.get("id"), "|", t.get("command"))
        else:
            print("test(str):", t)
    for a in r.get("artifacts", []) or []:
        if isinstance(a, dict):
            p = a.get("path", "")
            exists = os.path.isfile(REPO + "/" + p)
            print("  artifact:", p, "| exists:", exists, "| role:", a.get("role"))
