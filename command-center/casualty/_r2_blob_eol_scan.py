"""Scan every tracked blob under the lane for CRLF, so a `-text` attribute cannot freeze a
CRLF blob in place. Also reports what a Windows checkout would currently produce."""
import subprocess
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
files = subprocess.run(["git", "ls-files", "command-center/casualty/"], cwd=str(ROOT),
                       capture_output=True, text=True, check=True).stdout.split()
crlf_blobs, lf_blobs, crlf_worktree = [], [], []
for rel in files:
    blob = subprocess.run(["git", "cat-file", "-p", f"HEAD:{rel}"], cwd=str(ROOT),
                          capture_output=True, check=True).stdout
    (crlf_blobs if b"\r\n" in blob else lf_blobs).append(rel)
    p = ROOT / rel
    if p.is_file() and b"\r\n" in p.read_bytes():
        crlf_worktree.append(rel)

print(f"tracked lane files: {len(files)}")
print(f"blobs containing CRLF: {len(crlf_blobs)}")
for r in crlf_blobs:
    print(f"   {r}")
print(f"blobs pure LF: {len(lf_blobs)}")
print(f"WORKTREE files containing CRLF: {len(crlf_worktree)}")
for r in crlf_worktree:
    print(f"   {r}")
print("SUCCESS:blob-eol-scan safe to mark -text"
      if not crlf_blobs else "FAILED:blob-eol-scan a CRLF blob would be frozen by -text")
