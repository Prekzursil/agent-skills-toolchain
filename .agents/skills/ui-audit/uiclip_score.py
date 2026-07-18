#!/usr/bin/env python3
"""uiclip_score.py - OPTIONAL UIClip design-quality prior for ui-audit Track-B.

Scores a screenshot with the local UIClip model (biglab/uiclip-*, CLIP-based, MIT,
CPU-capable, ~600MB) into a single design-quality number for regression-gating and
best-of-N. It is a *weak numeric prior* only - the rubric critique works fully without it.

SAFETY CONTRACT (the user just hit an OOM - these are non-negotiable):
  * OPT-IN: scoring NEVER runs unless you pass --allow-download or --use-cache.
  * NO AUTO-DOWNLOAD: the ~600MB weights are only fetched with --allow-download.
  * RAM-GUARDED: refuses to load the model when free RAM < --min-free-gb (default 2.0)
    unless --force; if free RAM can't be measured it also refuses without --force.
  * GRACEFUL: on missing deps / no cache / low RAM / any error it prints a clean JSON
    object with status != "ok" and score=null and STILL EXITS 0, so the chain degrades
    to rubric-only instead of crashing.

stdout is ALWAYS a single JSON object (logs/markers go to stderr) so the harness can parse it.

Usage:
  python uiclip_score.py --check                       # report readiness, no load, no download
  python uiclip_score.py --screenshot home.png         # -> status:"skipped" (opt-in gate)
  python uiclip_score.py --screenshot home.png --use-cache       # score only if already cached
  python uiclip_score.py --screenshot home.png --allow-download  # fetch (~600MB) + score
  python uiclip_score.py --screenshot home.png --allow-download --out uiclip.json
"""

import argparse
import importlib.util
import json
import os
import sys

DEFAULT_MODEL = "biglab/uiclip-jitteredwebsites-2-224-paraphrased"
DEFAULT_PROCESSOR = "openai/clip-vit-base-patch32"
# UIClip scores design quality as image<->text similarity to a "well-designed" description.
DEFAULT_PROMPT = (
    "ui screenshot. a high quality, modern, professional, well-designed user interface."
)

REQUIRED = ("torch", "transformers", "PIL")


def probe_deps():
    """True/False per dep WITHOUT importing it (find_spec doesn't load the module)."""
    out = {}
    for name in REQUIRED + ("psutil",):
        try:
            out[name] = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            out[name] = False
    return out


def ram_status(min_free_gb):
    """Best-effort free-RAM check. ok=None means 'could not measure'."""
    try:
        import psutil  # noqa: PLC0415

        avail = psutil.virtual_memory().available / (1024**3)
        return {
            "available_gb": round(avail, 2),
            "min_free_gb": min_free_gb,
            "ok": avail >= min_free_gb,
            "source": "psutil",
        }
    except Exception:  # noqa: BLE001 - psutil absent or failed; degrade to 'unknown'
        return {
            "available_gb": None,
            "min_free_gb": min_free_gb,
            "ok": None,
            "source": "unknown",
        }


def model_cache_dir(model_id):
    """Return the HF hub cache dir for model_id if present, else None (import-free check)."""
    safe = "models--" + model_id.replace("/", "--")
    roots = []
    if os.environ.get("HF_HOME"):
        roots.append(os.path.join(os.environ["HF_HOME"], "hub"))
    if os.environ.get("HUGGINGFACE_HUB_CACHE"):
        roots.append(os.environ["HUGGINGFACE_HUB_CACHE"])
    roots.append(os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub"))
    for r in roots:
        p = os.path.join(r, safe)
        if os.path.isdir(p):
            return p
    return None


def emit(result, out_path=None):
    """Print the JSON result to stdout; optionally also write it to out_path. Always exit 0."""
    text = json.dumps(result, indent=2)
    if out_path:
        try:
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            print(f"[uiclip] WARN: could not write {out_path}: {exc}", file=sys.stderr)
    print(text)
    print(f"SUCCESS:uiclip-{result.get('status', 'unknown')}", file=sys.stderr)
    return 0


def compute_score(screenshot, model_id, processor_id, prompt, offline):
    """Load UIClip and return a design-quality score in [0,1]. Raises on failure."""
    if offline:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    import torch  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    from transformers import CLIPModel, CLIPProcessor  # noqa: PLC0415

    model = CLIPModel.from_pretrained(model_id)
    processor = CLIPProcessor.from_pretrained(processor_id)
    model.eval()
    image = Image.open(screenshot).convert("RGB")
    inputs = processor(text=[prompt], images=image, return_tensors="pt", padding=True)
    with torch.no_grad():
        img = torch.nn.functional.normalize(
            model.get_image_features(pixel_values=inputs["pixel_values"]), dim=-1
        )
        txt = torch.nn.functional.normalize(
            model.get_text_features(
                input_ids=inputs["input_ids"],
                attention_mask=inputs.get("attention_mask"),
            ),
            dim=-1,
        )
        cosine = float((img @ txt.T).squeeze().item())  # [-1, 1]
    return round((cosine + 1.0) / 2.0, 4)  # -> [0, 1]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Optional UIClip design-quality prior (opt-in, RAM-guarded)."
    )
    ap.add_argument("--screenshot", help="path to the screenshot to score")
    ap.add_argument("--out", help="also write the JSON result here")
    ap.add_argument(
        "--check",
        action="store_true",
        help="report readiness only (no load, no download)",
    )
    ap.add_argument(
        "--allow-download",
        action="store_true",
        help="permit fetching ~600MB weights, then score",
    )
    ap.add_argument(
        "--use-cache",
        action="store_true",
        help="score only if the model is already cached (no download)",
    )
    ap.add_argument("--force", action="store_true", help="override the RAM guard")
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="force the unavailable branch (deterministic test hook)",
    )
    ap.add_argument(
        "--min-free-gb",
        type=float,
        default=2.0,
        help="minimum free RAM to allow model load (default 2.0)",
    )
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--processor", default=DEFAULT_PROCESSOR)
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = ap.parse_args(argv)

    result = {
        "tool": "uiclip_score",
        "model": args.model,
        "screenshot": args.screenshot,
        "score": None,
    }

    # Deterministic test hook: behave as if the model stack is unavailable.
    if args.self_test or os.environ.get("UICLIP_FORCE_UNAVAILABLE") == "1":
        result.update(
            status="unavailable",
            reason="forced unavailable (self-test) — chain degrades to rubric-only",
        )
        return emit(result, args.out)

    deps = probe_deps()
    cached = model_cache_dir(args.model)

    # --check: readiness report, never loads or downloads.
    if args.check or not args.screenshot:
        ram = ram_status(args.min_free_gb)
        ready = all(deps[d] for d in REQUIRED) and ram.get("ok") is True
        result.update(
            status="ok",
            mode="check",
            deps=deps,
            ram=ram,
            model_cached=bool(cached),
            ready_to_score=ready,
            note=(
                "ready"
                if ready
                else "not ready — see deps/ram; scoring stays opt-in via --allow-download/--use-cache"
            ),
        )
        if not args.screenshot and not args.check:
            result["reason"] = "no --screenshot given; nothing to score"
        return emit(result, args.out)

    # Opt-in gate: nothing loads unless explicitly enabled.
    if not (args.allow_download or args.use_cache):
        result.update(
            status="skipped",
            reason="scoring is opt-in and RAM-heavy; pass --allow-download (fetch ~600MB + score) "
            "or --use-cache (score only if already cached). Track-B runs rubric-only without it.",
        )
        return emit(result, args.out)

    # Graceful: missing deps.
    missing = [d for d in REQUIRED if not deps[d]]
    if missing:
        result.update(
            status="unavailable",
            deps=deps,
            reason=f"missing python deps: {', '.join(missing)} — install torch+transformers+Pillow to enable",
        )
        return emit(result, args.out)

    # RAM guard (the OOM-safety the user asked for).
    ram = ram_status(args.min_free_gb)
    result["ram"] = ram
    if not args.force:
        if ram.get("ok") is False:
            result.update(
                status="skipped",
                reason=f"insufficient free RAM ({ram['available_gb']}GB < {args.min_free_gb}GB) — pass --force to override",
            )
            return emit(result, args.out)
        if ram.get("ok") is None:
            result.update(
                status="skipped",
                reason="cannot measure free RAM (psutil missing) — pass --force to proceed at your own risk",
            )
            return emit(result, args.out)

    # Cache gate for --use-cache (no network allowed).
    offline = args.use_cache and not args.allow_download
    if offline and not cached:
        result.update(
            status="unavailable",
            model_cached=False,
            reason="model not in HF cache and --use-cache forbids download — pass --allow-download to fetch",
        )
        return emit(result, args.out)

    # Actually score (guarded).
    try:
        score = compute_score(
            args.screenshot, args.model, args.processor, args.prompt, offline
        )
        result.update(
            status="ok",
            score=score,
            model_cached=bool(cached),
            offline=offline,
            note="design-quality prior in [0,1] (image<->'well-designed' text similarity); weak prior, not ground truth",
        )
    except Exception as exc:  # noqa: BLE001 - any load/inference failure degrades gracefully
        result.update(status="error", reason=f"{type(exc).__name__}: {exc}")
    return emit(result, args.out)


if __name__ == "__main__":
    sys.exit(main())
