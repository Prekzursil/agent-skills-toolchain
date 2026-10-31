import json, os
REPO = "C:/Users/Prekzursil/p2-g1"
for uid in ["IMP-0159", "IMP-0170", "IMP-0174", "IMP-0199", "IMP-0201", "IMP-0206"]:
    r = json.load(open(REPO + "/command-center/receipts/" + uid + ".json", encoding="utf-8"))
    print("=" * 30, uid)
    impl = r.get("implementation", {})
    mod = impl.get("module") or impl.get("artifact") or impl.get("path") or sorted(impl.keys())
    print("impl:", mod)
    for t in r.get("tests", []):
        print("test:", t.get("id"), "|", t.get("command"))
    for a in r.get("artifacts", []):
        p = a.get("path", "")
        exists = os.path.isfile(REPO + "/" + p)
        print("  artifact:", p, "| exists:", exists, "| role:", a.get("role"))
