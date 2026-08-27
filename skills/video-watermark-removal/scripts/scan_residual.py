#!/usr/bin/env python3
"""
Thorough residual-watermark scan. Builds a clean logo template from a source clip where
the logo sits on a dark uniform background (clip 16), then template-matches it across
MANY frames (full timeline) of every CLEANED output, full top-band, multi-scale. Reports
the MAX residual score per clip + the worst frame, and saves the worst-frame crop for any
clip above threshold. This catches a logo missed on some frames, an edge sliver, or a
mask that was mis-placed — things a single 50%-frame check misses.

Env knobs (all default to the razvan_gandu job, so a no-arg run is unchanged):
  RG       job root            (default /mnt/c/Users/Prekzursil/Downloads/razvan_gandu)
  QC       qc / output dir     (default /mnt/c/Users/Prekzursil/Downloads/wm_qc)
  SRC      watermarked sources (default $RG/shorts)
  CLN      cleaned outputs to scan (default $RG/shorts_clean)
  TPL_SRC  source clip with the logo on a dark bg, used to build the template
           (default $SRC/16_Polonia_vs_Romania_Succesul_dupa_1990.mp4)
  BBOX     "x0,y0,x1,y1" logo crop in TPL_SRC (default 23,78,210,145)
"""

import os
import json
import glob
import cv2
import numpy as np

RG = os.environ.get("RG", "/mnt/c/Users/Prekzursil/Downloads/razvan_gandu")
QC = os.environ.get("QC", "/mnt/c/Users/Prekzursil/Downloads/wm_qc")
SRC = os.environ.get("SRC", f"{RG}/shorts")
CLN = os.environ.get("CLN", f"{RG}/shorts_clean")
# logo over a dark blue bg -> clean template source
TPL_SRC = os.environ.get(
    "TPL_SRC", f"{SRC}/16_Polonia_vs_Romania_Succesul_dupa_1990.mp4"
)
BBOX = tuple(int(v) for v in os.environ.get("BBOX", "23,78,210,145").split(","))
SEARCH_YMAX = 220
SCALES = np.linspace(0.78, 1.18, 11)
NFRAMES = 14


def build_template():
    cap = cv2.VideoCapture(TPL_SRC)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(0.5 * n))
    ok, img = cap.read()
    cap.release()
    if not ok:
        raise SystemExit("cannot read template source")
    x0, y0, x1, y1 = BBOX
    roi = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    # logo is bright white on dark bg -> subtract local background, keep bright structure
    bg = cv2.GaussianBlur(roi, (0, 0), 9)
    pat = np.clip(roi - bg, 0, None)
    pat = pat - pat.min()
    if pat.max() > 0:
        pat = pat / pat.max() * 255.0
    cv2.imwrite(f"{QC}/_logo_tpl.png", pat.astype(np.uint8))
    return pat.astype(np.float32)


def best_score(gray, pat):
    band = gray[: min(SEARCH_YMAX, gray.shape[0]), :].astype(np.float32)
    bg = cv2.GaussianBlur(band, (0, 0), 9)
    band = np.clip(band - bg, 0, None)  # same high-pass as the template
    best, bb = -1.0, (0, 0, 0, 0)
    for s in SCALES:
        tw, th = int(pat.shape[1] * s), int(pat.shape[0] * s)
        if tw < 12 or th < 6 or tw >= band.shape[1] or th >= band.shape[0]:
            continue
        t = cv2.resize(pat, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(band, t, cv2.TM_CCOEFF_NORMED)
        res[~np.isfinite(res)] = -1
        _, mx, _, loc = cv2.minMaxLoc(res)
        if mx > best:
            best, bb = float(mx), (loc[0], loc[1], loc[0] + tw, loc[1] + th)
    return best, bb


def scan(path, pat):
    cap = cv2.VideoCapture(path)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    best, worst_img, at = -1.0, None, 0
    for i in range(NFRAMES):
        fr = int((i + 0.5) / NFRAMES * n)
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        ok, img = cap.read()
        if not ok:
            continue
        sc, _ = best_score(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), pat)
        if sc > best:
            best, worst_img, at = sc, img, fr
    cap.release()
    return best, worst_img, at


def main():
    os.makedirs(QC, exist_ok=True)
    pat = build_template()
    print(f"template {pat.shape[1]}x{pat.shape[0]}")
    clips = sorted(glob.glob(f"{SRC}/*.mp4"))
    rows = []
    # calibrate: source max scores (should be high)
    for s in clips:
        name = os.path.basename(s)
        c = f"{CLN}/{name}"
        ssc, _, _ = scan(s, pat)
        if not os.path.exists(c):
            rows.append(
                dict(clip=name[:40], src=round(ssc, 3), clean=None, v="MISSING")
            )
            continue
        csc, cimg, cat = scan(c, pat)
        # residual if cleaned still scores a meaningful fraction of source
        ratio = csc / ssc if ssc > 0 else 0
        v = "RESIDUAL" if (csc >= 0.35 and ratio >= 0.6) else "clean"
        rows.append(
            dict(
                clip=name[:40],
                src=round(ssc, 3),
                clean=round(csc, 3),
                ratio=round(ratio, 2),
                v=v,
                frame=cat,
            )
        )
        if v == "RESIDUAL" and cimg is not None:
            cv2.imwrite(f"{QC}/residual_{name[:2]}.png", cimg[40:175, 0:300])
    json.dump(rows, open(f"{QC}/scan.json", "w"), indent=2)
    print(f"{'clip':40s} {'src':>6} {'cln':>6} {'ratio':>6}  verdict")
    bad = 0
    for r in rows:
        if r["v"] != "clean":
            bad += 1
        print(
            f"{r['clip']:40s} {str(r['src']):>6} {str(r['clean']):>6} {str(r.get('ratio', '')):>6}  {r['v']}{'  <===' if r['v'] != 'clean' else ''}"
        )
    print(
        f"\nGENUINE RESIDUAL/MISSING: {bad}/{len(rows)}  (saved residual_NN.png crops for any)"
    )


if __name__ == "__main__":
    main()
