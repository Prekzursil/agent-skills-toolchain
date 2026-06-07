"""Live end-to-end test suite for unrestricted mode. Run directly:
    .venv/Scripts/python.exe tests/test_live.py
Prints PASS/FAIL. Network-dependent.
"""
import os
import sys
import tempfile


def _load_env():
    envf = os.path.expanduser("~/.tooluniverse/.env")
    if os.path.exists(envf):
        for line in open(envf, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


_load_env()
from scholarly_access import logic, policy  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


print("=== Scholarly Access MCP — live test suite (UNRESTRICTED) ===\n")

# 1. DOI resolution
r = logic.resolve("10.1371/journal.pmed.0020124")
check("DOI resolution", r.get("resolved"), (r.get("metadata", {}).get("title") or "")[:50])

# 2. PMID resolution
r = logic.resolve("16060722")
check("PMID resolution", r.get("resolved"), (r.get("metadata", {}).get("title") or "")[:50])

# 3. arXiv resolution
r = logic.resolve("1706.03762")
check("arXiv resolution", r.get("resolved"), (r.get("metadata", {}).get("title") or "")[:50])

# 4. title search
r = logic.resolve("Attention is all you need")
check("title search → DOI/metadata", r.get("resolved"), "doi=" + str(r.get("identifiers", {}).get("doi")))

# 5. OA PDF discovery
oa = logic.find_oa_pdf(doi="10.1371/journal.pmed.0020124")
check("PDF discovery", bool(oa.get("oa_pdf_url")), (oa.get("oa_pdf_url") or "")[:60])

# 6. PDF download (arXiv)
ax = logic.find_oa_pdf(arxiv="1706.03762")
dl = {"ok": False}
if ax.get("oa_pdf_url"):
    with tempfile.TemporaryDirectory() as td:
        dl = logic.download_oa_pdf(ax["oa_pdf_url"], dest_dir=td, source="arxiv")
check("PDF download (real %PDF + sha256)", dl.get("ok") and dl.get("sha256"),
      f"{dl.get('bytes',0)//1024}KB" if dl.get("ok") else dl.get("error", "")[:60])

# 7. unrestricted access status
a = logic.access_status(doi="10.1056/NEJMoa2034577")
check("access status checking", a.get("status") in (policy.OA_PDF, policy.SUBSCRIPTION, policy.FREE_NOT_REDIST, policy.UNAVAILABLE),
      a.get("status"))

# 8. batch resolve
b = logic.batch_resolve(["10.1371/journal.pmed.0020124", "1706.03762", "this-is-not-a-real-paper-xyzzy-000"])
check("batch resolve (table + unresolved)", b.get("count") == 3 and b.get("resolved") >= 2 and len(b.get("unresolved", [])) >= 1,
      f"{b.get('resolved')}/3 resolved")

# 9. citation graph
c = logic.citation_graph(doi="10.1371/journal.pmed.0020124")
check("citation graph", c.get("source") is not None,
      f"refs={c['counts']['references']} cites={c['counts']['cited_by']}")

passed = sum(1 for _, ok in results if ok)
print(f"\n=== {passed}/{len(results)} live checks passed ===")
sys.exit(0 if passed == len(results) else 1)
