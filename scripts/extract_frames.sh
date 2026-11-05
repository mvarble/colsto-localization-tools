#!/usr/bin/env bash
# Extract the video stills referenced by the docs into frames/.
#   scripts/extract_frames.sh [path/to/video.webm]
# Default video: the *[UytYrhYLOKI].webm in the repo root (see scripts/fetch_video.sh).
# Needs: ffmpeg.
set -euo pipefail
cd "$(dirname "$0")/.."

VIDEO="${1:-$(ls ./*"[UytYrhYLOKI]".webm 2>/dev/null | head -n1)}"
[[ -f "$VIDEO" ]] || { echo "video not found; run scripts/fetch_video.sh or pass a path" >&2; exit 1; }
OUT=frames
WIDTH=1280
mkdir -p "$OUT"

grab() {  # grab <mm:ss> <outfile> <width>
  ffmpeg -v error -y -ss "00:$1" -i "$VIDEO" -frames:v 1 -vf "scale=$3:-1" -q:v 4 "$2"
}

# Single stills: timestamp -> frames/<m>_<ss>.jpg
for t in 1:01 1:24 1:44 3:12 4:03 4:26 7:14 9:19 18:32 21:31 22:38 26:42; do
  grab "$(printf '%05s' "$t" | tr ' ' 0)" "$OUT/${t/:/_}.jpg" "$WIDTH"
done

# Data-source montage: FR24 site (3:03), pyfr24 repo (3:07), all flights in QGIS (3:20), 2x2 grid
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
for t in 3:03 3:07 3:20; do
  grab "0$t" "$tmp/${t/:/_}.jpg" 960
done
ffmpeg -v error -y -i "$tmp/3_03.jpg" -i "$tmp/3_07.jpg" -i "$tmp/3_20.jpg" \
  -filter_complex "[0][1][2]xstack=inputs=3:layout=0_0|w0_0|0_h0:fill=black[o]" \
  -map "[o]" -q:v 4 "$OUT/3_03-3_20_sources.jpg"

ls -1 "$OUT"
