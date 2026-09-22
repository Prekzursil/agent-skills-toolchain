#!/usr/bin/env bash
# Independent digest reproduction for IMP-0002 (adversarial reviewer).
# Builds from SECOND_CHECKOUT only. Does not read implementer measurements.
set -euo pipefail

SECOND_CHECKOUT="${1:?second checkout path}"
REVIEW_DIR="${2:?review artifact dir}"
REV="${3:-HEAD}"

mkdir -p "$REVIEW_DIR/work"
PACK_PY="$SECOND_CHECKOUT/tools/plugin/pack.py"
ALLOW="$SECOND_CHECKOUT/tools/plugin/payload-allowlist.json"

echo "INDEPENDENT BUILDS 1+2 FROM SECOND CHECKOUT" | tee "$REVIEW_DIR/build12.raw.txt"
echo "repo=$SECOND_CHECKOUT" | tee -a "$REVIEW_DIR/build12.raw.txt"
echo "rev=$REV" | tee -a "$REVIEW_DIR/build12.raw.txt"
git -C "$SECOND_CHECKOUT" rev-parse "$REV" | tee -a "$REVIEW_DIR/build12.raw.txt"

OUT1="$REVIEW_DIR/work/build1.zip"
OUT2="$REVIEW_DIR/work/build2.zip"

# Build 1
python3 -B "$PACK_PY" \
  --repo "$SECOND_CHECKOUT" \
  --rev "$REV" \
  --allowlist "$ALLOW" \
  --prefix tools/plugin \
  --out "$OUT1" \
  --json | tee "$REVIEW_DIR/build1.pack.json"

# Build 2 (same checkout, clean deterministic mode)
python3 -B "$PACK_PY" \
  --repo "$SECOND_CHECKOUT" \
  --rev "$REV" \
  --allowlist "$ALLOW" \
  --prefix tools/plugin \
  --out "$OUT2" \
  --json | tee "$REVIEW_DIR/build2.pack.json"

# Hash with openssl/sha256sum independently of pack JSON
H1=$(sha256sum "$OUT1" | awk '{print $1}')
H2=$(sha256sum "$OUT2" | awk '{print $1}')
echo "build1_sha256=$H1" | tee -a "$REVIEW_DIR/build12.raw.txt"
echo "build2_sha256=$H2" | tee -a "$REVIEW_DIR/build12.raw.txt"
if [ "$H1" = "$H2" ]; then EQ=true; else EQ=false; fi
echo "equal_12=$EQ" | tee -a "$REVIEW_DIR/build12.raw.txt"

python3 - <<PY
import json
from pathlib import Path
review = Path(r"""$REVIEW_DIR""")
h1 = """$H1"""
h2 = """$H2"""
meas = {
    "build1_sha256": h1,
    "build2_sha256": h2,
    "equal": h1 == h2,
    "repo": r"""$SECOND_CHECKOUT""",
    "rev": r"""$REV""",
}
(review / "build12-measurement.json").write_text(
    json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(meas, indent=2, sort_keys=True))
PY

# Build 3 via separate hasher script (different cwd/TMPDIR/clock)
python3 -B "$(dirname "$0")/independent_build3_hasher.py" \
  --repo "$SECOND_CHECKOUT" \
  --rev "$REV" \
  --out-dir "$REVIEW_DIR" \
  --clock-offset-seconds 7200
