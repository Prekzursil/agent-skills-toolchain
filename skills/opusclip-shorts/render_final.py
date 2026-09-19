# -*- coding: utf-8 -*-
"""Final render: OpusClip-matched style (SINGLE-LAYER timed color-flip karaoke),
corrected Romanian captions, face-tracked 9:16, #N naming, Romanian titles."""
import json, os, subprocess, sys, time
import numpy as np
import cv2

SRC = r"C:\Users\Prekzursil\Downloads\2026-09-13-AIUD-Puric-MAH00119.MP4"
W = json.load(open("shorts-work/words.json", encoding="utf-8"))
CLIPS = json.load(open("shorts-work/clips.json", encoding="utf-8"))
CORR = json.load(open("shorts-work/corrections.json", encoding="utf-8"))
OUTDIR = "shorts-out"
os.makedirs(OUTDIR, exist_ok=True)

SEED = {"02": 0.22, "03": 0.40, "04": 0.42, "08": 0.26, "09": 0.50, "10": 0.50}

# chronological numbering continues the user's OpusClip set (#1..#44); Romanian titles
FINAL = [
 {"id":"10","num":9,  "file":"#9 Nocturna celulara_ versurile din temnita ale bunicului",
  "title":"Nocturnă celulară — versurile din temniță ale bunicului"},
 {"id":"02","num":19, "file":"#19 La ce sa se adapteze, domnisoara_ raspunsul lui Emil Botta",
  "title":"La ce să se adapteze, domnișoară? — răspunsul lui Emil Botta"},
 {"id":"08","num":20, "file":"#20 Imbecilul are un punct de vedere_ scara lui Hilbert",
  "title":"Imbecilul are un punct de vedere — scara lui Hilbert"},
 {"id":"03","num":22, "file":"#22 Ne-ati expropia inteligenta_ Micescu si martirii de la Aiud",
  "title":"Ne-ați expropia inteligența — Micescu și martirii de la Aiud"},
 {"id":"04","num":29, "file":"#29 Eu traiesc in veac_ taranul lui Ernest Bernea",
  "title":"Eu trăiesc în veac — țăranul lui Ernest Bernea"},
 {"id":"09","num":48, "file":"#48 Drept sau dreptate_ fara transcendentza",
  "title":"Drept sau dreptate — fără transcendență"},
]

def ass_time(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"

HDR = (
    "[Script Info]\n"
    "ScriptType: v4.00+\n"
    "PlayResX: 1080\n"
    "PlayResY: 1920\n"
    "WrapStyle: 0\n"
    "ScaledBorderAndShadow: yes\n\n"
    "[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
    "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
    "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    "Style: Karaoke,Arial Black,66,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,1.2,0,"
    "1,3,1.4,2,70,70,420,1\n\n"
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
)

GREEN = "\\c&H35E2D8&\\fscx106\\fscy106"
WHITE = "\\c&HFFFFFF&\\fscx100\\fscy100"

def build_ass(cid, w0, w1, t0):
    corr = CORR.get(cid, {})
    words = []
    for i in range(w0, w1 + 1):
        txt = corr.get(str(i), W[i]["w"])
        if txt == "": continue
        words.append(dict(w=txt, t=W[i]["t"] - t0, e=W[i]["e"] - t0))
    cues, cur = [], []
    for x in words:
        if cur:
            gap = x["t"] - cur[-1]["e"]
            joined = len(" ".join(c["w"] for c in cur + [x]))
            if gap > 0.65 or x["t"] - cur[0]["t"] > 3.2 or len(cur) >= 4 or joined > 26:
                cues.append(cur); cur = []
        cur.append(x)
    if cur: cues.append(cur)
    lines = [HDR]
    for i, cue in enumerate(cues):
        start = max(0.0, cue[0]["t"] - 0.12)
        end = cue[-1]["e"] + 0.35
        if i + 1 < len(cues):
            end = min(end, cues[i+1][0]["t"] - 0.05)
        end = max(end, start + 0.3)
        ts, te = ass_time(start), ass_time(end)
        # ONE layer, ONE dialogue per cue: per-word timed color flip. Color changes
        # cannot shift layout -> exactly ONE subtitle block at all times (OpusClip look:
        # spoken words white, current word yellow-green with a quick 106% pop).
        parts = []
        for x in cue:
            a = max(0, int((x["t"] - start) * 1000))
            b = int((x["e"] - start) * 1000) + 120
            parts.append("{\\t(%d,%d,%s)\\t(%d,%d,%s)}%s " % (a, a + 30, GREEN, b, b + 150, WHITE, x["w"].upper()))
        text = "".join(parts).strip()
        lines.append("Dialogue: 0,%s,%s,Karaoke,,0,0,0,,%s\n" % (ts, te, text))
    p = f"shorts-work/subs_{cid}.ass"
    open(p, "w", encoding="utf-8-sig").write("".join(lines))
    return p

def track_crop(cid, start, dur, seed_pct):
    cap = cv2.VideoCapture(SRC)
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000.0)
    n_frames = int(dur * 25)
    frontal = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    profile = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    det_t, det_x = [], []
    prev_cx = seed_pct * 1280
    fi = 0
    while fi < n_frames:
        ok, frame = cap.read()
        if not ok: break
        if fi % 12 == 0:
            small = cv2.resize(frame, (640, 360))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            best = None
            for flip in (False, True):
                g = cv2.flip(gray, 1) if flip else gray
                for cascade in (frontal, profile):
                    for (x, y, w2, h2) in cascade.detectMultiScale(g, 1.12, 5, minSize=(24, 24)):
                        cx = (x + w2 / 2) * 2
                        if flip: cx = 1280 - cx
                        score = w2 * h2 - abs(cx - prev_cx) * 1.2
                        if best is None or score > best[0]: best = (score, cx)
                    if best: break
                if best: break
            if best:
                det_t.append(fi / 25.0); det_x.append(best[1]); prev_cx = best[1]
        fi += 1
    cap.release()
    if not det_x:
        xs = np.full(n_frames, seed_pct * 1280)
    else:
        det_t = np.array(det_t); det_x = np.array(det_x)
        sm = np.array([np.median(det_x[np.abs(det_t - tt) <= 2.0]) for tt in det_t])
        tgt = np.interp(np.arange(n_frames) / 25.0, det_t, sm)
        xs = np.zeros(n_frames); cur = tgt[0]
        for i in range(n_frames):
            d = tgt[i] - cur
            if abs(d) > 60: cur += d * 0.06
            elif abs(d) >= 25: cur += d * 0.02
            xs[i] = cur
    return np.clip(xs, 0, 1280 - 405)

def render(fc):
    c = next(x for x in CLIPS if x["id"] == fc["id"])
    cid, start, dur = fc["id"], c["start"], c["end"] - c["start"]
    w0, w1 = c["w0"], c["w1"]
    sub = build_ass(cid, w0, w1, start)
    xs = track_crop(cid, start, dur, SEED[cid])
    print(f"[{fc['num']}] {fc['file']}: {start:.1f}+{dur:.1f}s crop[{xs.min():.0f}..{xs.max():.0f}] mean {xs.mean():.0f}", flush=True)
    p1 = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", SRC,
         "-map", "0:v", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        stdout=subprocess.PIPE)
    out = os.path.join(OUTDIR, fc["file"] + ".mp4")
    p2 = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "1080x1920", "-r", "25", "-i", "-",
         "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", SRC,
         "-map", "0:v", "-map", "1:a",
         "-vf", f"ass={sub},unsharp=5:5:0.35:3:3:0.0",
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-r", "25",
         "-metadata", f"title={fc['title']} — Dan Puric / Aiud 2026",
         "-metadata", "language=ron",
         "-movflags", "+faststart", out],
        stdin=subprocess.PIPE)
    nbytes = 1280 * 720 * 3
    fi = 0
    def readn(n):
        buf = b""
        while len(buf) < n:
            b = p1.stdout.read(n - len(buf))
            if not b: break
            buf += b
        return buf
    while fi < len(xs):
        buf = readn(nbytes)
        if len(buf) < nbytes: break
        frame = np.frombuffer(buf, np.uint8).reshape(720, 1280, 3)
        x = int(round(xs[fi]))
        big = cv2.resize(frame[:, x:x+405], (1080, 1920), interpolation=cv2.INTER_LANCZOS4)
        p2.stdin.write(big.tobytes())
        fi += 1
    p1.stdout.close(); p2.stdin.close(); p2.wait(); p1.wait()
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{dur*0.45:.2f}", "-i", out, "-frames:v", "1", "-q:v", "3",
                    os.path.join(OUTDIR, fc["file"] + ".jpg")])
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
                         "-of", "default=nw=1", out], capture_output=True, text=True)
    print(f"[{fc['num']}] DONE\n{pr.stdout.strip()}", flush=True)

sel = [f["id"] for f in FINAL if f["id"] in (sys.argv[1:] or [f["id"] for f in FINAL])]
for fc in FINAL:
    if fc["id"] in sel:
        render(fc)
