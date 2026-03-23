#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path


def classify(path_text: str) -> str:
    if path_text.startswith("\\\\"):
        return "unc"
    suffix = Path(path_text).suffix.lower()
    if suffix in {".vhdx", ".vmdk", ".vdi"}:
        return "disk-image"
    if suffix in {".tar", ".tgz", ".tar.gz"}:
        return "archive"
    if path_text.startswith("/mnt/"):
        return "wsl-mounted-windows"
    if path_text.startswith("/"):
        return "posix"
    if len(path_text) > 2 and path_text[1:3] == ":\\":
        return "windows-drive"
    return "unknown"


def recommend(source: str, target: str) -> dict:
    s_kind = classify(source)
    t_kind = classify(target)
    if "disk-image" in {s_kind, t_kind}:
        return {"mechanism": "offline-attach", "reason": "guest disk image involved", "source_kind": s_kind, "target_kind": t_kind}
    if t_kind == "archive":
        return {"mechanism": "tar", "reason": "target is an archive artifact", "source_kind": s_kind, "target_kind": t_kind}
    if s_kind == "windows-drive" and t_kind == "windows-drive":
        return {"mechanism": "robocopy", "reason": "both endpoints are Windows-visible", "source_kind": s_kind, "target_kind": t_kind}
    return {"mechanism": "rsync", "reason": "directory-tree copy with resumability and excludes", "source_kind": s_kind, "target_kind": t_kind}


def watch_file(path_text: str, interval: float, samples: int) -> dict:
    path = Path(path_text)
    history = []
    for _ in range(samples):
        size = path.stat().st_size if path.exists() else 0
        now = time.time()
        history.append((now, size))
        print(f"t={now:.0f} size={size}")
        time.sleep(interval)
    first_t, first_size = history[0]
    last_t, last_size = history[-1]
    delta_t = max(last_t - first_t, 1e-6)
    return {
        "path": str(path),
        "start_size": first_size,
        "end_size": last_size,
        "bytes_per_second": (last_size - first_size) / delta_t,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Recommend copy strategy or watch file growth.")
    sub = parser.add_subparsers(dest="command", required=True)

    recommend_parser = sub.add_parser("recommend", help="Recommend a copy mechanism.")
    recommend_parser.add_argument("--source", required=True)
    recommend_parser.add_argument("--target", required=True)

    watch_parser = sub.add_parser("watch-file", help="Watch file size growth.")
    watch_parser.add_argument("path")
    watch_parser.add_argument("--interval", type=float, default=2.0)
    watch_parser.add_argument("--samples", type=int, default=5)

    args = parser.parse_args()
    if args.command == "recommend":
        print(json.dumps(recommend(args.source, args.target), indent=2))
        return 0
    result = watch_file(args.path, args.interval, args.samples)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
