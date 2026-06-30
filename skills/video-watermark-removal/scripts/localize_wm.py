#!/usr/bin/env python3
"""
Localize the OpusClip watermark in each clip and emit a per-clip rectangular mask.

Strategy (robust to the semi-transparent white logo):
  - Sample N frames from ~START_SEC onward (past intro hooks).
  - Build a per-pixel temporal-median "static" image: the static, semi-transparent
    logo persists; the (slightly) moving foreground/face averages out. The logo
    stands out cleanly for matching.
  - Multi-scale template match (TM_CCORR_NORMED with the logo's alpha as a mask, so
    only the logo pixels are correlated -> background-invariant) on the median image
    AND on individual frames; vote for the best/stable bbox.
  - Confidence = best normalized score. Below threshold OR implausible position ->
    fall back to a sensible top-center box that avoids the source/branding bars, and FLAG.
  - Mask = filled white rect (bbox + margin) on black, clamped so it never touches the
    top "Sursa: ..." bar. Save mask PNG + (for samples/flagged) an overlay preview.
"""

import os
import sys
import json
import glob
import cv2
import numpy as np

IN_DIR = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "/mnt/c/Users/Prekzursil/Downloads/razvan_gandu/shorts"
)
MASK_DIR = (
    sys.argv[2]
    if len(sys.argv) > 2
    else "/mnt/c/Users/Prekzursil/Downloads/razvan_gandu/masks"
)
PREV_DIR = (
    sys.argv[3] if len(sys.argv) > 3 else "/mnt/c/Users/Prekzursil/Downloads/wm_qc"
)
TPL_PATH = (
    sys.argv[4]
    if len(sys.argv) > 4
    else "/mnt/c/Users/Prekzursil/Downloads/opus_logo_template.png"
)

START_SEC = 7.0  # skip intro hooks
N_SAMPLES = 14  # frames sampled per clip
# the OpusClip overlay is the same render in every clip -> size is ~constant. keep scales tight.
SCALES = np.linspace(0.80, 1.12, 9)
MARGIN = 7  # px padding around matched bbox
TOP_PROTECT = 62  # mask top is never allowed above this (protects "Sursa:" bar)
SEARCH_YMAX = 200  # only search the top band for the logo
SEARCH_XFRAC = (
    0.62  # logo is left-of/around center; cap match x0 to this fraction of width
)
CONF_THRESH = (
    0.33  # TM_CCOEFF_NORMED score considered confident (mean-subtracted -> lower scale)
)
# generous fallback box (covers observed logo positions across clips, clear of bars)
FALLBACK = dict(x0=30, y0=86, x1=244, y1=150)


def load_template(path):
    """Return the logo's *additive brightness pattern* (alpha*255) as a single-channel
    float template. TM_CCOEFF_NORMED on this is invariant to background DC/scale, so it
    localizes the logo shape rather than 'any bright patch'."""
    tpl = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if tpl is None:
        raise SystemExit(f"cannot read template {path}")
    if tpl.ndim == 3 and tpl.shape[2] == 4:
        alpha = tpl[:, :, 3].astype(np.float32)  # transparency -> logo coverage
        bgr = tpl[:, :, :3].astype(np.float32)
        lum = cv2.cvtColor(bgr.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
        pat = alpha * (lum / 255.0)  # bright-where-opaque-logo
        mask = (tpl[:, :, 3] > 20).astype(np.uint8) * 255
    else:
        g = (cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY) if tpl.ndim == 3 else tpl).astype(
            np.float32
        )
        pat = g
        mask = (g > 60).astype(np.uint8) * 255
    # normalize to 0..255 float
    pat = pat - pat.min()
    if pat.max() > 0:
        pat = pat / pat.max() * 255.0
    return pat.astype(np.float32), mask


def sample_frames(path):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    start = int(START_SEC * fps)
    end = max(start + 1, total - int(0.5 * fps))
    if end <= start:
        start, end = 0, max(1, total - 1)
    idxs = np.linspace(start, end, N_SAMPLES).astype(int)
    frames = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, fr = cap.read()
        if ok:
            frames.append(fr)
    cap.release()
    return frames, fps, total, w, h


def best_match(gray_img, tpl_pat, tpl_mask):
    """Multi-scale TM_CCOEFF_NORMED on the logo's brightness pattern (mean-subtracted ->
    background-DC invariant). Search restricted to the top-left band so bright foreheads /
    captions elsewhere cannot win. Returns (score, x0, y0, x1, y1, scale)."""
    H, W = gray_img.shape[:2]
    img = gray_img.astype(np.float32)
    band = img[: min(SEARCH_YMAX, H), :]
    best = (-1.0, 0, 0, 0, 0, 1.0)
    for s in SCALES:
        tw = int(round(tpl_pat.shape[1] * s))
        th = int(round(tpl_pat.shape[0] * s))
        if tw < 12 or th < 6 or tw >= band.shape[1] or th >= band.shape[0]:
            continue
        t = cv2.resize(tpl_pat, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(band, t, cv2.TM_CCOEFF_NORMED)
        res[~np.isfinite(res)] = -1
        # forbid matches whose left edge is past SEARCH_XFRAC (logo is left-of-center)
        xcap = int(W * SEARCH_XFRAC)
        if xcap < res.shape[1]:
            res[:, xcap:] = -1
        _, mx, _, mxloc = cv2.minMaxLoc(res)
        if mx > best[0]:
            best = (
                float(mx),
                mxloc[0],
                mxloc[1],
                mxloc[0] + tw,
                mxloc[1] + th,
                float(s),
            )
    return best


def main():
    os.makedirs(MASK_DIR, exist_ok=True)
    os.makedirs(PREV_DIR, exist_ok=True)
    prev_all = os.path.join(MASK_DIR, "previews")
    os.makedirs(prev_all, exist_ok=True)
    tpl_pat, tpl_mask = load_template(TPL_PATH)
    print(
        f"template {tpl_pat.shape[1]}x{tpl_pat.shape[0]} mask-px={(tpl_mask > 0).sum()}"
    )
    clips = sorted(glob.glob(os.path.join(IN_DIR, "*.mp4")))
    rows = []
    sample_names = {"01_Romania_in_Pericol", "05_Romania_Actioneaza"}
    for path in clips:
        name = os.path.basename(path)
        frames, fps, total, W, H = sample_frames(path)
        if not frames:
            print(f"!! {name}: no frames")
            continue
        gframes = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
        median = np.median(np.stack(gframes), axis=0).astype(np.uint8)

        # primary signal = match on the static temporal-median image
        score, x0, y0, x1, y1, scale = best_match(median, tpl_pat, tpl_mask)
        # confirm against individual frames; count agreement near the median's center
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        agree = 0
        for g in gframes[::2]:
            s2, ax0, ay0, ax1, ay1, _ = best_match(g, tpl_pat, tpl_mask)
            if (
                s2 > CONF_THRESH * 0.8
                and abs((ax0 + ax1) / 2 - cx) < 30
                and abs((ay0 + ay1) / 2 - cy) < 25
            ):
                agree += 1

        # plausibility: logo must sit in the top band, left-of/around center
        plausible = (
            (TOP_PROTECT - 8 <= y0)
            and (y1 <= SEARCH_YMAX + 10)
            and (x0 < W * SEARCH_XFRAC)
        )
        flagged = (score < CONF_THRESH) or (not plausible) or (agree < 2)
        if flagged:
            x0, y0, x1, y1 = (
                FALLBACK["x0"],
                FALLBACK["y0"],
                FALLBACK["x1"],
                FALLBACK["y1"],
            )

        # expand by margin, clamp, protect top bar
        mx0 = max(0, x0 - MARGIN)
        my0 = max(TOP_PROTECT, y0 - MARGIN)
        mx1 = min(W, x1 + MARGIN)
        my1 = min(H, y1 + MARGIN)

        mask = np.zeros((H, W), np.uint8)
        mask[my0:my1, mx0:mx1] = 255
        mask_path = os.path.join(MASK_DIR, os.path.splitext(name)[0] + ".png")
        cv2.imwrite(mask_path, mask)

        row = dict(
            clip=name,
            score=round(score, 4),
            scale=round(scale, 3),
            agree=int(agree),
            bbox=[int(mx0), int(my0), int(mx1), int(my1)],
            raw_bbox=[int(x0), int(y0), int(x1), int(y1)],
            flagged=bool(flagged),
            fps=round(fps, 2),
            frames=int(total),
            w=W,
            h=H,
        )
        rows.append(row)
        tag = "FLAG" if flagged else "ok  "
        print(
            f"[{tag}] {name[:42]:42s} score={score:.3f} scale={scale:.2f} agree={agree} mask={row['bbox']}"
        )

        # overlay preview for every clip (so localization can be eyeballed)
        ov = frames[len(frames) // 2].copy()
        cv2.rectangle(ov, (mx0, my0), (mx1, my1), (0, 255, 0), 2)
        shade = ov.copy()
        shade[my0:my1, mx0:mx1] = (0, 0, 255)
        ov = cv2.addWeighted(shade, 0.3, ov, 0.7, 0)
        cv2.imwrite(
            os.path.join(prev_all, "overlay_" + os.path.splitext(name)[0] + ".png"), ov
        )
        if flagged or any(name.startswith(p) for p in sample_names):
            cv2.imwrite(
                os.path.join(PREV_DIR, "overlay_" + os.path.splitext(name)[0] + ".png"),
                ov,
            )

    with open(os.path.join(MASK_DIR, "_localization.json"), "w") as f:
        json.dump(rows, f, indent=2)
    n_flag = sum(r["flagged"] for r in rows)
    print(
        f"\nDONE {len(rows)} clips, {n_flag} flagged -> {MASK_DIR}/_localization.json"
    )


if __name__ == "__main__":
    main()
