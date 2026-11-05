#!/usr/bin/env bash
# Download the source video and its English subtitles (auto-generated + original) into the repo root.
# Produces:
#   I discovered a sound that leaks your exact location (and it's everywhere) [UytYrhYLOKI].webm
#   ... [UytYrhYLOKI].en.srt, ... [UytYrhYLOKI].en-orig.srt
# Needs: yt-dlp, ffmpeg (for merging and subtitle conversion). ~700 MB at 2160p.
set -euo pipefail
cd "$(dirname "$0")/.."

URL="https://www.youtube.com/watch?v=UytYrhYLOKI"

yt-dlp \
  -f "bv*[height<=2160]+ba/b" --merge-output-format webm \
  --write-subs --write-auto-subs --sub-langs "en,en-orig" --convert-subs srt \
  -o "%(title)s [%(id)s].%(ext)s" \
  "$URL"
