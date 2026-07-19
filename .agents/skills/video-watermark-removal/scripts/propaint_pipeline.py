#!/usr/bin/env python3
"""
Per-frame, time-aware, CHUNKED ProPainter watermark removal (v4).
v4 fix: ProPainter loads a whole video + all-frame optical flow into RAM -> OOM (SIGKILL)
on long clips. So we process in time-CHUNKS (bounded RAM): each core window gets a few
context frames on each side for temporal propagation, ProPainter runs per chunk, and only
the core frames are composited back. Chunks whose masks are all empty (logo absent, e.g.
hook card) skip ProPainter entirely.

Also: logo POSITION is localized once (robust median match); per-frame PRESENCE gates the
mask (logo absent -> empty mask -> frame left pristine). Composite blends ONLY the masked
logo pixels (feathered) + a mild unsharp; original audio re-muxed.

Usage: propaint_pipeline.py <in.mp4> <out.mp4> [start_sec] [dur_sec]
Env knobs (all optional; defaults keep the razvan_gandu job unchanged):
  TPL_GRAY     clean logo template PNG
               (default /mnt/c/Users/Prekzursil/Downloads/wm_qc/_logo_gray.png)
  PP           ProPainter checkout dir (default ~/ProPainter)
  DET_THRESH   logo-localization detect threshold (default 0.30)
  PRES_THRESH  per-frame presence threshold (default 0.18)
  CORE         core frames per time-chunk (default 450)
  CTXF         context frames on each side of a chunk (default 20)
"""

import os
import sys
import shutil
import subprocess
import tempfile
import cv2
import numpy as np

INP, OUTP = sys.argv[1], sys.argv[2]
START = float(sys.argv[3]) if len(sys.argv) > 3 else None
DUR = float(sys.argv[4]) if len(sys.argv) > 4 else None
TPL_GRAY = os.environ.get(
    "TPL_GRAY", "/mnt/c/Users/Prekzursil/Downloads/wm_qc/_logo_gray.png"
)
DET_THRESH = float(os.environ.get("DET_THRESH", "0.30"))
PRES_THRESH = float(os.environ.get("PRES_THRESH", "0.18"))
CORE = int(os.environ.get("CORE", "450"))
CTXF = int(os.environ.get("CTXF", "20"))
PP = os.path.expanduser(os.environ.get("PP", "~/ProPainter"))
SEARCH_YMAX, SEARCH_XFRAC = 220, 0.62
SCALES = np.linspace(0.85, 1.16, 9)
CTX, DILATE = 70, 7


def hp(g):
    g = g.astype(np.float32)
    return np.clip(g - cv2.GaussianBlur(g, (0, 0), 11), 0, None)


def load_tpl():
    g = cv2.imread(TPL_GRAY, cv2.IMREAD_GRAYSCALE)
    pat = hp(g)
    pat = pat - pat.min()
    pat = pat / max(pat.max(), 1) * 255.0
    alpha = (g > 140).astype(np.uint8) * 255
    return pat.astype(np.float32), alpha


def ncc(sub, tmpl):
    a = hp(sub)
    if a.shape != tmpl.shape:
        a = cv2.resize(a, (tmpl.shape[1], tmpl.shape[0]))
    res = cv2.matchTemplate(a, tmpl.astype(np.float32), cv2.TM_CCOEFF_NORMED)
    return float(res.max()) if res.size else -1.0


def best_match(band, pat, W):
    best = (-1.0, 0, 0, 1.0)
    for s in SCALES:
        tw, th = int(pat.shape[1] * s), int(pat.shape[0] * s)
        if tw < 12 or th < 6 or tw >= band.shape[1] or th >= band.shape[0]:
            continue
        t = cv2.resize(pat, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(band, t, cv2.TM_CCOEFF_NORMED)
        res[~np.isfinite(res)] = -1
        xc = int(W * SEARCH_XFRAC)
        if xc < res.shape[1]:
            res[:, xc:] = -1
        _, mx, _, loc = cv2.minMaxLoc(res)
        if mx > best[0]:
            best = (float(mx), loc[0], loc[1], float(s))
    return best


def run_propainter(frames_dir, masks_dir, outdir, fps):
    subprocess.run(
        [
            "python",
            f"{PP}/inference_propainter.py",
            "-i",
            frames_dir,
            "-m",
            masks_dir,
            "-o",
            outdir,
            "--fp16",
            "--subvideo_length",
            "80",
            "--mask_dilation",
            "0",
            "--save_fps",
            str(int(round(fps))),
        ],
        cwd=PP,
        check=True,
    )
    for root, _, fls in os.walk(outdir):
        for f in fls:
            if f == "inpaint_out.mp4":
                return os.path.join(root, f)
    raise SystemExit("ProPainter output not found")


def main():
    pat, alpha = load_tpl()
    tmp = tempfile.mkdtemp(prefix="pp_")
    comp, fdir, mdir = f"{tmp}/comp", f"{tmp}/frames", f"{tmp}/masks"
    for d in (comp, fdir, mdir):
        os.makedirs(d)
    rate = (
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=r_frame_rate",
                "-of",
                "csv=p=0",
                INP,
            ]
        )
        .decode()
        .strip()
        .split("/")
    )
    fps = float(rate[0]) / float(rate[1])
    dec = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y"]
    if START is not None:
        dec += ["-ss", str(START)]
    if DUR is not None:
        dec += ["-t", str(DUR)]
    dec += ["-i", INP]
    subprocess.run(dec + [f"{comp}/%06d.png"], check=True)
    frames = sorted(os.listdir(comp))
    n = len(frames)
    H, W = cv2.imread(f"{comp}/{frames[0]}").shape[:2]

    # robust fixed localization from temporal median of post-intro frames
    idx = [int(n * f) for f in np.linspace(0.30, 0.92, 18)]
    med = np.median(
        np.stack(
            [
                cv2.cvtColor(cv2.imread(f"{comp}/{frames[i]}"), cv2.COLOR_BGR2GRAY)
                for i in idx
            ]
        ),
        0,
    ).astype(np.uint8)
    sc, x, y, s = best_match(hp(med)[:SEARCH_YMAX, :], pat, W)
    tw, th = int(pat.shape[1] * s), int(pat.shape[0] * s)
    if sc < DET_THRESH:
        shutil.copy(INP, OUTP)
        shutil.rmtree(tmp)
        print(f"NO-LOGO {os.path.basename(OUTP)} score={sc:.2f} (copied)")
        return

    aw = (
        cv2.resize(
            (alpha > 0).astype(np.uint8), (tw, th), interpolation=cv2.INTER_NEAREST
        )
        * 255
    )
    fixed = np.zeros((H, W), np.uint8)
    y1, x1 = min(H, y + th), min(W, x + tw)
    fixed[y:y1, x:x1] = aw[: y1 - y, : x1 - x]
    fixed = cv2.dilate(fixed, np.ones((DILATE, DILATE), np.uint8))
    tpat = cv2.resize(pat, (tw, th), interpolation=cv2.INTER_AREA)

    rx0, ry0 = max(0, x - CTX), max(0, y - CTX)
    rx1, ry1 = min(W, x1 + CTX), min(H, y1 + CTX)
    rw, rh = ((rx1 - rx0) // 8) * 8, ((ry1 - ry0) // 8) * 8
    rx1, ry1 = rx0 + rw, ry0 + rh

    # per-frame ROI frames + presence-gated masks
    present = [False] * n
    for k, fn in enumerate(frames):
        img = cv2.imread(f"{comp}/{fn}")
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        p = ncc(g[y:y1, x:x1], tpat) >= PRES_THRESH
        present[k] = p
        cv2.imwrite(f"{fdir}/{fn}", img[ry0:ry1, rx0:rx1])
        m = fixed if p else np.zeros((H, W), np.uint8)
        cv2.imwrite(f"{mdir}/{fn}", m[ry0:ry1, rx0:rx1])
    npres = sum(present)

    fa = cv2.GaussianBlur(fixed.astype(np.float32), (0, 0), 2.0) / 255.0
    fa_roi = np.clip(fa[ry0:ry1, rx0:rx1], 0, 1)[:, :, None]

    # CHUNKED ProPainter + composite (bounded RAM)
    a = 0
    while a < n:
        b = min(n, a + CORE)
        es, ee = max(0, a - CTXF), min(n, b + CTXF)
        win = frames[es:ee]
        if not any(present[es:ee]):
            a = b
            continue  # no logo in this window -> core frames stay original
        cf, cm = f"{tmp}/cf", f"{tmp}/cm"
        for d in (cf, cm):
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d)
        for j, fn in enumerate(win):
            shutil.copy(f"{fdir}/{fn}", f"{cf}/{j:06d}.png")
            shutil.copy(f"{mdir}/{fn}", f"{cm}/{j:06d}.png")
        outdir = f"{tmp}/pp"
        shutil.rmtree(outdir, ignore_errors=True)
        ppvid = run_propainter(cf, cm, outdir, fps)
        cap = cv2.VideoCapture(ppvid)
        outframes = []
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            outframes.append(fr)
        cap.release()
        for k in range(a, b):
            if not present[k]:
                continue
            oi = k - es
            if oi >= len(outframes):
                continue
            pp = outframes[oi]
            if pp.shape[:2] != (rh, rw):
                pp = cv2.resize(pp, (rw, rh))
            fn = frames[k]
            full = cv2.imread(f"{comp}/{fn}")
            region = full[ry0:ry1, rx0:rx1].astype(np.float32)
            ppf = pp.astype(np.float32)
            ppf = cv2.addWeighted(ppf, 1.4, cv2.GaussianBlur(ppf, (0, 0), 1.4), -0.4, 0)
            full[ry0:ry1, rx0:rx1] = np.clip(
                region * (1 - fa_roi) + np.clip(ppf, 0, 255) * fa_roi, 0, 255
            ).astype(np.uint8)
            cv2.imwrite(f"{comp}/{fn}", full)
        a = b

    tmpv = f"{tmp}/v.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            str(int(round(fps))),
            "-i",
            f"{comp}/%06d.png",
            "-c:v",
            "libx264",
            "-crf",
            "17",
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
            tmpv,
        ],
        check=True,
    )
    amux = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", tmpv]
    if START is not None:
        amux += ["-ss", str(START)]
    if DUR is not None:
        amux += ["-t", str(DUR)]
    amux += [
        "-i",
        INP,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0?",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        "-shortest",
        OUTP,
    ]
    subprocess.run(amux, check=True)
    shutil.rmtree(tmp)
    print(
        f"DONE {os.path.basename(OUTP)} frames={n} present={npres} loc_score={sc:.2f} ROI={rw}x{rh}"
    )


if __name__ == "__main__":
    main()
