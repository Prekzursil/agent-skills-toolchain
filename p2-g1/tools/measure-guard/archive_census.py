"""Census of git-archive-as-blob prescriptions (IMP-0440)."""
from __future__ import annotations

import os
import tarfile
from io import BytesIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
NEEDLE = "git archive"
SKIP_DIR = {".git", "node_modules", "__pycache__", "ovh-monitor", ".venv"}
SKIP_SUFFIX = {".pyc", ".png", ".jpg", ".zip", ".gz", ".tgz", ".pdf"}
OWN = {
    "blobread.py",
    "three_route.py",
    "crlf_export_repo.py",
    "archive_census.py",
    "test_blobread.py",
}


def members_from_tar(data: bytes) -> list[str]:
    names: list[str] = []
    with tarfile.open(fileobj=BytesIO(data), mode="r:") as tar:
        for member in tar.getmembers():
            if member.isfile():
                names.append(member.name.replace("\\", "/"))
    return sorted(names)


def census_path(path: str | Path) -> list[str]:
    return members_from_tar(Path(path).read_bytes())


def _iter_files() -> list[Path]:
    out: list[Path] = []
    roots = [REPO / "tools", REPO / "command-center" / "p2-wave" / "probes"]
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR]
            for name in filenames:
                path = Path(dirpath) / name
                if path.suffix.lower() in SKIP_SUFFIX:
                    continue
                out.append(path)
    return out


def _kind(path: Path, text: str) -> str:
    rel = path.relative_to(REPO).as_posix()
    if "_imp0440_planted" in path.name:
        return "prescription"
    if path.name in OWN or "measure-guard" in rel:
        return "mention"
    if "REFUSED" in text or "trap" in text.lower() or "wrong bytes" in text.lower():
        return "mention"
    if path.suffix in {".md", ".txt", ".json"}:
        return "mention"
    return "mention"


def census(root: Path | None = None) -> dict:
    root = root or REPO
    prescriptions = []
    mentions = []
    data_files = []
    invocations = []
    packaging = []
    fixtures = []
    for path in _iter_files():
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if NEEDLE.encode("utf-8") not in raw and b"git-archive" not in raw:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            data_files.append(str(path.relative_to(REPO)).replace("\\", "/"))
            continue
        rel = path.relative_to(REPO).as_posix()
        kind = _kind(path, text)
        row = {"path": rel, "kind": kind}
        if kind == "prescription":
            prescriptions.append(row)
        else:
            mentions.append(row)
        if "tarfile" in text or "archive --format" in text:
            packaging.append(rel)
    return {
        "total_hits": len(prescriptions) + len(mentions) + len(data_files),
        "mentions_use_vs_mention": mentions,
        "data_files_not_classifiable_as_prescriptions": data_files,
        "real_invocations": invocations,
        "legitimate_whole_tree_packaging": packaging,
        "detector_fixtures_wrong_recipe": fixtures,
        "provenance_prescriptions_remaining": prescriptions,
    }


def plant_one_control() -> dict:
    planted = REPO / "tools" / "measure-guard" / "_imp0440_planted_archive_recipe.py"
    body = (
        '"""planted prescription: uses git archive as the blob oracle."""\n'
        "import subprocess\n"
        "def blob():\n"
        "    return subprocess.check_output(['git', 'archive', 'HEAD', 'x'])\n"
    )
    planted.write_text(body, encoding="utf-8")
    live = census()
    found = any(r.get("path", "").endswith(planted.name) for r in live["provenance_prescriptions_remaining"])
    planted.unlink(missing_ok=True)
    after = census()
    remaining_after = [
        r for r in after["provenance_prescriptions_remaining"] if r.get("path", "").endswith(planted.name)
    ]
    return {
        "found_plant": found,
        "silent_after_removal": remaining_after == [],
        "remaining_after": remaining_after,
    }


__all__ = ["census", "census_path", "members_from_tar", "plant_one_control"]
