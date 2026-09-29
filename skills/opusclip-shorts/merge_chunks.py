#!/usr/bin/env python
"""merge_chunks.py — split long-video audio into overlapping ASR chunks and merge
per-chunk transcripts (words[] with start/end) into ONE absolute-time words.json.

Usage:
  python merge_chunks.py split  <SRC_VIDEO> <OUT_AUDIO_DIR> [chunk_s=720] [overlap_s=4]
      -> writes chunkN.wav + manifest.json  (then transcribe each chunk with your
         harness's word-level ASR MCP, one output_json per chunk: t0..tN.json)
  python merge_chunks.py merge <OUT_AUDIO_DIR> <WORDS_JSON>
      -> merges t*.json using the boundary rule and writes words.json

Boundary rule (word-cut safe): chunk i contributes words with end <= (i+1)*chunk_s;
chunk i+1 contributes words with end > i*chunk_s. A word spanning a boundary is taken
from the LATER chunk (its copy is complete); garbage near a chunk's hard stop is never used.
"""
import json, os, subprocess, sys

def split(src, outdir, ch, ov):
    os.makedirs(outdir, exist_ok=True)
    dur = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                                "-of","csv=p=0",src], capture_output=True, text=True).stdout.strip())
    n = int(dur // ch) + (1 if dur % ch > 1 else 0)
    man = []
    for i in range(n):
        start = 0.0 if i == 0 else i*ch - ov
        end = min(dur, i*ch + ch); d = end - start
        out = os.path.join(outdir, f"chunk{i}.wav")
        subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-ss",f"{start:.3f}",
                        "-t",f"{d:.3f}","-i",src,"-vn","-ac","1","-ar","16000",
                        "-c:a","pcm_s16le",out], check=True)
        man.append({"i":i,"start":start,"dur":d,"boundary":(i+1)*ch,"file":out})
        print(f"chunk{i}: {start:.1f}+{d:.1f}s")
    json.dump(man, open(os.path.join(outdir,"manifest.json"),"w"), indent=1)

def merge(outdir, words_out):
    man = json.load(open(os.path.join(outdir,"manifest.json"), encoding="utf-8"))
    allw = []
    for m in man:
        tp = os.path.join(outdir, f"t{m['i']}.json")
        d = json.load(open(tp, encoding="utf-8"))
        for seg in d.get("segments", []):
            for w in seg.get("words", []):
                if w.get("start") is None: continue
                allw.append({"t": m["start"]+w["start"], "e": m["start"]+w["end"],
                             "w": w["text"], "ci": m["i"]})
    B = {m["i"]: m["boundary"] for m in man}
    merged = []
    for w in sorted(allw, key=lambda x: (x["e"], x["t"])):
        ci = w["ci"]
        if ci in B and w["e"] > B[ci] + 0.001: continue          # belongs to next chunk's copy
        if ci > 0 and w["e"] <= B[ci-1] + 0.001: continue        # already covered by prev chunk
        merged.append(w)
    merged.sort(key=lambda x: x["t"])
    json.dump(merged, open(words_out,"w",encoding="utf-8"), ensure_ascii=False)
    print(f"merged {len(allw)} -> {len(merged)} words -> {words_out}")
    # readable transcript for moment-picking
    lines, cur, last = [], [], None
    for w in merged:
        if last is not None and (w["t"]-last > 0.9 or
           (cur and cur[-1][0].rstrip().endswith((".","!","?","…")) and
            len(" ".join(x[0] for x in cur)) > 60)):
            lines.append(cur); cur = []
        cur.append((w["w"], w["t"])); last = w["e"]
    if cur: lines.append(cur)
    with open(words_out.replace(".json","_readable.txt"),"w",encoding="utf-8") as f:
        for c in lines:
            t = c[0][1]; h,mn,s = int(t//3600), int(t%3600//60), int(t%60)
            f.write(f"[{h:02d}:{mn:02d}:{s:02d}] " + " ".join(x[0] for x in c) + "\n")
    print("readable transcript written")

if __name__ == "__main__":
    if sys.argv[1] == "split": split(sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv)>4 else 720.0, float(sys.argv[5]) if len(sys.argv)>5 else 4.0)
    elif sys.argv[1] == "merge": merge(sys.argv[2], sys.argv[3])
