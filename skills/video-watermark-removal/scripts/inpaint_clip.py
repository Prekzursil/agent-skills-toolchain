#!/usr/bin/env python3
"""
Remove the OpusClip watermark from ONE clip with big-LAMA inpainting (per-frame).

  decode (ffmpeg rawvideo RGB) -> LAMA fills the masked logo region on a context band
  -> composite ONLY the masked region back onto the untouched frame with a feathered
  edge (seamless, no residual logo) -> encode H264 crf -> re-mux the ORIGINAL audio.

Only the mask region is ever altered; everything else (Sursa bar, branding, captions,
face, body) is bit-for-bit the original. Output keeps the source WxH.

Usage: inpaint_clip.py <in.mp4> <mask.png> <out.mp4> [crf=18]
"""
import sys
import os
import json
import time
import subprocess
import numpy as np
import cv2
import torch

INP   = sys.argv[1]
MASKP = sys.argv[2]
OUTP  = sys.argv[3]
CRF   = sys.argv[4] if len(sys.argv) > 4 else "18"
MODEL = os.environ.get("LAMA_MODEL", os.path.expanduser("~/wm_models/big-lama.pt"))
CTX_PAD = 140          # vertical context (px) given to LAMA around the mask band
FEATHER = 3.0          # gaussian sigma for the composite edge
MOD = 8


def ffprobe(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", path])
    s = json.loads(out)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), float(num) / float(den)


def pad_to(v, m=MOD):
    return v + (m - v % m) % m


def main():
    W, H, FPS = ffprobe(INP)
    mask = cv2.imread(MASKP, cv2.IMREAD_GRAYSCALE)
    if mask is None or mask.shape != (H, W):
        raise SystemExit(f"mask {MASKP} shape {None if mask is None else mask.shape} != {(H, W)}")

    ys, xs = np.where(mask > 0)
    if len(ys) == 0:
        raise SystemExit("empty mask")
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    cy0 = max(0, y0 - CTX_PAD)
    cy1 = min(H, y1 + CTX_PAD)
    bh, bw = cy1 - cy0, W                      # context band: full width
    ph, pw = pad_to(bh), pad_to(bw)

    # feathered alpha: =1 over the whole mask (logo fully covered), ramps in a dilated margin
    dil = cv2.dilate(mask, np.ones((9, 9), np.uint8))
    alpha = cv2.GaussianBlur(dil.astype(np.float32), (0, 0), FEATHER) / 255.0
    alpha = np.clip(alpha, 0, 1)
    alpha_band = alpha[cy0:cy1, :, None]        # bh,bw,1

    mask_band = (mask[cy0:cy1, :] > 0).astype(np.float32)
    mask_pt = torch.zeros(1, 1, ph, pw)
    mask_pt[0, 0, :bh, :bw] = torch.from_numpy(mask_band)
    mask_pt = mask_pt.cuda()

    model = torch.jit.load(MODEL).eval().cuda()

    dec = subprocess.Popen(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-i", INP,
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE)
    tmp = OUTP + ".noaudio.mp4"
    enc = subprocess.Popen(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", f"{FPS}", "-i", "-",
         "-c:v", "libx264", "-crf", CRF, "-preset", "medium", "-pix_fmt", "yuv420p", tmp],
        stdin=subprocess.PIPE)

    fsize = W * H * 3
    img_pt = torch.zeros(1, 3, ph, pw, device="cuda")
    n = 0
    t0 = time.time()
    with torch.no_grad():
        while True:
            raw = dec.stdout.read(fsize)
            if len(raw) < fsize:
                break
            frame = np.frombuffer(raw, np.uint8).reshape(H, W, 3).copy()   # RGB
            band = frame[cy0:cy1, :].astype(np.float32) / 255.0
            img_pt.zero_()
            img_pt[0, :, :bh, :bw] = torch.from_numpy(band).permute(2, 0, 1).cuda()
            out = model(img_pt, mask_pt)                                    # 1,3,ph,pw 0..1
            filled = out[0, :, :bh, :bw].permute(1, 2, 0).clamp(0, 1).cpu().numpy() * 255.0
            comp = band * 255.0 * (1 - alpha_band) + filled * alpha_band
            frame[cy0:cy1, :] = np.clip(comp, 0, 255).astype(np.uint8)
            enc.stdin.write(frame.tobytes())
            n += 1
    enc.stdin.close()
    dec.wait()
    enc.wait()

    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", tmp, "-i", INP,
         "-map", "0:v:0", "-map", "1:a:0?", "-c:v", "copy", "-c:a", "copy",
         "-movflags", "+faststart", "-shortest", OUTP], check=True)
    os.remove(tmp)
    dt = time.time() - t0
    print(f"DONE {os.path.basename(OUTP)} frames={n} {dt:.1f}s {n/max(dt,1e-9):.1f}fps "
          f"band={bw}x{bh}->{pw}x{ph}")


if __name__ == "__main__":
    main()
