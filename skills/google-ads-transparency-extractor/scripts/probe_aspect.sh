#!/bin/bash
# Metadata-only probe of every resolved video (no video data downloaded), then bucket by aspect.
#   ./probe_aspect.sh <dir>
set -u
D="${1:-.}"; S="$(cd "$(dirname "$0")" && pwd)"
yt-dlp --batch-file "$D/youtube_ids.txt" --skip-download --no-warnings --ignore-errors \
  --sleep-requests 0.3 \
  --print "%(id)s|%(width)s|%(height)s|%(duration)s|%(title)s" > "$D/dims_raw.txt" 2> "$D/dims.err"
echo "PROBE DONE: $(wc -l < "$D/dims_raw.txt" | tr -d ' ') of $(wc -l < "$D/youtube_ids.txt" | tr -d ' ')"
python3 "$S/probe_aspect.py" "$D"
