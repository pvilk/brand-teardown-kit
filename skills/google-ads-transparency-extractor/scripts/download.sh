#!/bin/bash
# Download YouTube ad videos as PLAYABLE mp4 (H.264 + AAC). Resumable. Verifies at the end.
#   ./download.sh <dir> [ids_file] [outdir_name]
# e.g. ./download.sh ./brand-google-ads ids_16x9_landscape.txt landscape_16x9
set -u
D="${1:-.}"; IDS="${2:-youtube_ids.txt}"; OUT="${3:-videos}"
cd "$D" || exit 1
mkdir -p "$OUT"
ARCHIVE="archive_$(basename "$IDS" .txt).txt"; touch "$ARCHIVE"

# HARD filter, not -S. `-S codec:avc1` is only a PREFERENCE and silently falls back to
# AV1/VP9 + Opus, which --merge-output-format mp4 will happily wrap in an .mp4 that
# QuickTime cannot open. This chain forces avc1 video + mp4a audio.
FMT="bv*[vcodec^=avc1]+ba[acodec^=mp4a]/bv*[vcodec^=avc1]+ba/b[vcodec^=avc1]/bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b"

for pass in 1 2 3; do
  echo "########## PASS $pass ##########"
  find "$OUT" -name '*.part' -delete 2>/dev/null   # stale .part => 403 on resume
  yt-dlp --batch-file "$IDS" --download-archive "$ARCHIVE" \
    --no-abort-on-error --ignore-errors --no-warnings --no-progress \
    -N 2 --retries 10 --fragment-retries 10 --sleep-requests 0.5 \
    -f "$FMT" -S "res:1080" --merge-output-format mp4 \
    --postprocessor-args "Merger:-c:v copy -c:a aac -b:a 192k -movflags +faststart" \
    --restrict-filenames -o "$OUT/%(id)s__%(title).70s.%(ext)s" 2>&1 \
    | grep -viE '^\[download\]|^\[info\]|Deleting original'
  have=$(ls "$OUT"/*.mp4 2>/dev/null | wc -l | tr -d ' ')
  want=$(grep -c . "$IDS")
  echo "--- pass $pass: $have / $want ---"
  [ "$have" -ge "$want" ] && break
done

# Stragglers: HD itags can 403 on every default client. mweb often serves when default won't.
ls "$OUT"/*.mp4 2>/dev/null | sed 's|.*/||' | cut -c1-11 | sort > /tmp/_got.$$
sort "$IDS" > /tmp/_want.$$
for id in $(comm -13 /tmp/_got.$$ /tmp/_want.$$); do
  echo "--- straggler $id: trying alternate clients ---"
  for C in mweb android_vr tv_embedded web_embedded; do
    find "$OUT" -name '*.part' -delete 2>/dev/null
    yt-dlp "$id" --no-warnings --no-progress --no-continue --retries 5 \
      --extractor-args "youtube:player_client=$C" \
      -f "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/b[vcodec^=avc1]/22/18/b" -S "res:1080" \
      --merge-output-format mp4 \
      --postprocessor-args "Merger:-c:v copy -c:a aac -b:a 192k -movflags +faststart" \
      --restrict-filenames -o "$OUT/%(id)s__%(title).70s.%(ext)s" >/dev/null 2>&1
    ls "$OUT" | cut -c1-11 | grep -qxF "$id" && { echo "    recovered via $C"; break; }
  done
done
rm -f /tmp/_got.$$ /tmp/_want.$$
find "$OUT" -name '*.part' -o -name '*.ytdl' -delete 2>/dev/null

echo; echo "=== VERIFY (codec AND resolution -- a codec-only check passes a 360p fallback) ==="
bad=0
for f in "$OUT"/*.mp4; do
  [ -e "$f" ] || continue
  v=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$f" 2>/dev/null | head -1)
  wh=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$f" 2>/dev/null | head -1)
  a=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$f" 2>/dev/null | head -1)
  flag=""
  if [ "$v" != "h264" ] || [ "$a" != "aac" ]; then flag="  <-- NOT PLAYABLE"; bad=$((bad+1)); fi
  printf "%-50s %-6s %-11s %-5s %6s%s\n" "$(basename "$f" .mp4 | cut -c1-48)" "$v" "$wh" "${a:-NONE}" "$(du -h "$f" | cut -f1)" "$flag"
done
echo
echo "files: $(ls "$OUT"/*.mp4 2>/dev/null | wc -l | tr -d ' ')  |  not h264+aac: $bad  |  size: $(du -sh "$OUT" 2>/dev/null | cut -f1)"
[ "$bad" -gt 0 ] && echo "!! re-run: those fell back to a codec QuickTime cannot open"
exit 0
