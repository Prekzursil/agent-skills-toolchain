#!/usr/bin/env python3
"""
Reliable "prove it's clean" gate for the v2/v4 outputs. For each clip:
  - localize the logo on the SOURCE (fixed pos + scale) using the clean logo template;
  - sample many frames of the OUTPUT; at the fixed logo bbox, measure NCC vs the logo
    template. Output NCC must be LOW on every sampled frame -> logo gone. A high output
    NCC = RESIDUAL (logo left in).
  - sharpness ratio: Laplacian variance of the treated patch vs a clean neighbor patch
    (catches soft/blurry fills). ratio near 1 = good.
Writes {QC}/verify.json; prints a table; exit code 1 if any clip fails.

Env knobs (all default to the razvan_gandu job, so a no-arg run is unchanged):
  RG        job root            (default /mnt/c/Users/Prekzursil/Downloads/razvan_gandu)
  QC        qc / output dir     (default /mnt/c/Users/Prekzursil/Downloads/wm_qc)
  SRC       watermarked sources (default $RG/shorts)
  OUT       cleaned outputs to verify (default $RG/shorts_clean_v2)
  TPL_GRAY  clean logo template PNG   (default $QC/_logo_gray.png)
  NCC_FAIL  residual-NCC fail threshold (default 0.42)
  SHARP_MIN min sharpness ratio        (default 0.45)
"""

import os
import sys
import json
import glob
import cv2
import numpy as np

RG = os.environ.get("RG", "/mnt/c/Users/Prekzursil/Downloads/razvan_gandu")
QC = os.environ.get("QC", "/mnt/c/Users/Prekzursil/Downloads/wm_qc")
SRC = os.environ.get("SRC", f"{RG}/shorts")
OUT = os.environ.get("OUT", f"{RG}/shorts_clean_v2")
TPL_GRAY = os.environ.get("TPL_GRAY", f"{QC}/_logo_gray.png")
NCC_FAIL = float(os.environ.get("NCC_FAIL", "0.42"))
SHARP_MIN = float(os.environ.get("SHARP_MIN", "0.45"))
SCALES = np.linspace(0.85, 1.16, 9)
NF = 16


def hp(g):
    g = g.astype(np.float32)
    return np.clip(g - cv2.GaussianBlur(g, (0, 0), 11), 0, None)


def lv(a):
    return cv2.Laplacian(a, cv2.CV_64F).var()


def tpl():
    g = cv2.imread(TPL_GRAY, cv2.IMREAD_GRAYSCALE)
    p = hp(g)
    p -= p.min()
    p = p / max(p.max(), 1) * 255.0
    return p.astype(np.float32)


def localize(path, pat):
    cap = cv2.VideoCapture(path)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    stk = []
    for f in np.linspace(0.3, 0.92, 14):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * f))
        ok, im = cap.read()
        if ok:
            stk.append(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
    cap.release()
    med = np.median(np.stack(stk), 0).astype(np.uint8)
    W = med.shape[1]
    band = hp(med)[:220, :]
    best = (-1.0, 0, 0, 1.0)
    for s in SCALES:
        tw, th = int(pat.shape[1] * s), int(pat.shape[0] * s)
        if tw < 12 or th < 6 or tw >= band.shape[1] or th >= band.shape[0]:
            continue
        r = cv2.matchTemplate(band, cv2.resize(pat, (tw, th)), cv2.TM_CCOEFF_NORMED)
        r[~np.isfinite(r)] = -1
        xc = int(W * 0.62)
        if xc < r.shape[1]:
            r[:, xc:] = -1
        _, mx, _, loc = cv2.minMaxLoc(r)
        if mx > best[0]:
            best = (float(mx), loc[0], loc[1], float(s))
    return best


def out_ncc(path, pat, x, y, tw, th):
    cap = cv2.VideoCapture(path)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    t = cv2.resize(pat, (tw, th))
    mx = -1.0
    sharp = []
    for f in np.linspace(0.05, 0.95, NF):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * f))
        ok, im = cap.read()
        if not ok:
            continue
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        sub = hp(g[max(0, y - 6) : y + th + 6, max(0, x - 6) : x + tw + 6])
        if sub.shape[0] >= th and sub.shape[1] >= tw:
            r = cv2.matchTemplate(sub, t, cv2.TM_CCOEFF_NORMED)
            if r.size:
                mx = max(mx, float(r.max()))
        tp = g[y : y + th, x : x + tw]
        nb = g[y : y + th, x + tw + 8 : x + 2 * tw + 8]
        if tp.size and nb.shape == tp.shape and lv(nb) > 1:
            sharp.append(lv(tp) / lv(nb))
    cap.release()
    return mx, (float(np.median(sharp)) if sharp else None)


def main():
    pat = tpl()
    rows = []
    fails = 0
    for s in sorted(glob.glob(f"{SRC}/*.mp4")):
        name = os.path.basename(s)
        o = f"{OUT}/{name}"
        if not os.path.exists(o):
            rows.append(dict(clip=name[:38], v="MISSING"))
            fails += 1
            continue
        sc, x, y, sk = localize(s, pat)
        tw, th = int(pat.shape[1] * sk), int(pat.shape[0] * sk)
        oncc, sharp = out_ncc(o, pat, x, y, tw, th)
        resid = oncc >= NCC_FAIL
        soft = sharp is not None and sharp < SHARP_MIN
        v = "FAIL-RESIDUAL" if resid else ("WARN-SOFT" if soft else "clean")
        if v.startswith("FAIL"):
            fails += 1
        rows.append(
            dict(
                clip=name[:38],
                loc=round(sc, 2),
                out_ncc=round(oncc, 3),
                sharp=(round(sharp, 2) if sharp else None),
                v=v,
            )
        )
    json.dump(rows, open(f"{QC}/verify.json", "w"), indent=2)
    print(f"{'clip':38s} {'loc':>5} {'outNCC':>7} {'sharp':>6}  verdict")
    for r in rows:
        mark = "" if r.get("v") == "clean" else "  <==="
        print(
            f"{r['clip']:38s} {str(r.get('loc', '')):>5} {str(r.get('out_ncc', '')):>7} {str(r.get('sharp', '')):>6}  {r.get('v')}{mark}"
        )
    print(f"\nFAILs: {fails}/{len(rows)}  (NCC_FAIL={NCC_FAIL} SHARP_MIN={SHARP_MIN})")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
