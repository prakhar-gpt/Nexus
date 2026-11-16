#!/usr/bin/env bash
# Nexus LinkedIn cut. Change the numbers in this block, then re-run:
#   bash build.sh
set -euo pipefail
cd "$(dirname "$0")"

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

INPUT="/c/Users/praxc/Videos/Screen Recordings/Screen Recording 2026-11-12 215301.mp4"
MUSIC="./music.mp3"
OUTPUT="./output.mp4"

# Source is already the app window (1918x928). Full-frame crop, then pad.
CROP_X=0
CROP_Y=0
CROP_W=1918
CROP_H=928

# Clip source ranges, in seconds. Speeds match the brief.
# 1 intro / upload at 2x. Login (about 11.8-15.2) is left out.
S1A_START=0.60    # landing headline
S1A_END=8.60
S1B_START=15.40   # welcome / how it works
S1B_END=21.00
S1C_START=21.15   # empty room through upload checks
S1C_END=33.10
SPEED1=2

# 2 schema approval at 3x. Ends before the Teams toast (~48.2).
S2_START=33.15
S2_END=47.60
SPEED2=3

# 3 typing + thinking at 4x, through "Running Python calculation..."
S3_START=59.20
S3_END=92.95
SPEED3=4

# 4 answer on screen at 1x. The number is only up for ~1.5s before the
# click, so ANSWER_HOLD freezes that frame so it can be read.
S4_START=93.05
S4_END=94.60
SPEED4=1
ANSWER_HOLD=6

# 5 click, trace panel, "Show the query", at 1x.
# QUERY_HOLD freezes the SQL frame so the query can be read.
S5_START=94.60
S5_END=106.30
SPEED5=1
QUERY_HOLD=4

XFADE=0.30
FADE_IN=0.50
FADE_OUT=0.80

# Trace panel in source pixels. Zoom eases to ZOOM_MAX, then back out.
# Lower half of the trace panel, so the SQL stays inside the 1.6x frame.
ZOOM_X=1476
ZOOM_Y=250
ZOOM_W=430
ZOOM_H=580
ZOOM_MAX=1.6
ZOOM_EASE=0.60
ZOOM_IN_AT=0.85
# Zoom-out begins this many seconds before segment 5 ends.
ZOOM_OUT_LEAD=1.40

# Outline around the clicked figure 122,033.54, in source pixels.
HL_X=842
HL_Y=652
HL_W=120
HL_H=28
HL_START=0.35
HL_DUR=2.0
HL_RADIUS=6

# Cover the account email in the sidebar footer. Landing URL, clip A only.
EMAIL_X=18
EMAIL_Y=891
EMAIL_W=252
EMAIL_H=16
EMAIL_COLOR="0x28282A"
URL_X=0
URL_Y=908
URL_W=270
URL_H=20

OUT_W=1080
OUT_H=1350
FPS=30
PAD_COLOR="0x0A0A0A"
CRF=18
MUSIC_DB=-18
MUSIC_FADE_IN=1
MUSIC_FADE_OUT=2

# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is not on PATH. Install it, then re-run." >&2
  exit 1
fi
if ! command -v ffprobe >/dev/null 2>&1; then
  echo "ffprobe is not on PATH." >&2
  exit 1
fi
if ! command -v python >/dev/null 2>&1; then
  echo "python is not on PATH (needed to draw the highlight)." >&2
  exit 1
fi
if [[ ! -f "$INPUT" ]]; then
  echo "Input video not found: $INPUT" >&2
  exit 1
fi
if [[ ! -f "$MUSIC" ]]; then
  echo "Music not found: $MUSIC" >&2
  echo "Put the royalty-free mp3 at video/music.mp3 (or edit MUSIC) and re-run." >&2
  exit 1
fi

mkdir -p .build

export CROP_X CROP_Y CROP_W CROP_H \
  S1A_START S1A_END S1B_START S1B_END S1C_START S1C_END SPEED1 \
  S2_START S2_END SPEED2 \
  S3_START S3_END SPEED3 \
  S4_START S4_END SPEED4 ANSWER_HOLD \
  S5_START S5_END SPEED5 QUERY_HOLD \
  XFADE FADE_IN FADE_OUT \
  ZOOM_X ZOOM_Y ZOOM_W ZOOM_H ZOOM_MAX ZOOM_EASE ZOOM_IN_AT ZOOM_OUT_LEAD \
  HL_X HL_Y HL_W HL_H HL_START HL_DUR HL_RADIUS \
  EMAIL_X EMAIL_Y EMAIL_W EMAIL_H EMAIL_COLOR \
  URL_X URL_Y URL_W URL_H \
  OUT_W OUT_H FPS PAD_COLOR MUSIC_DB MUSIC_FADE_IN MUSIC_FADE_OUT

python - <<'PY'
import os
from PIL import Image, ImageDraw

def f(name):
    return float(os.environ[name])

def i(name):
    return int(os.environ[name])

fps = i("FPS")
crop_w, crop_h = i("CROP_W"), i("CROP_H")
xfade = f("XFADE")
fade_in = f("FADE_IN")
fade_out = f("FADE_OUT")

def clip_dur(start, end, speed, hold):
    return (end - start) / speed + hold

clips = [
    # label, start, end, speed, hold, covers
    ("a", f("S1A_START"), f("S1A_END"), f("SPEED1"), 0.0, "url"),
    ("b", f("S1B_START"), f("S1B_END"), f("SPEED1"), 0.0, "email"),
    ("c", f("S1C_START"), f("S1C_END"), f("SPEED1"), 0.0, "email"),
    ("d", f("S2_START"), f("S2_END"), f("SPEED2"), 0.0, "email"),
    ("e", f("S3_START"), f("S3_END"), f("SPEED3"), 0.0, "email"),
    ("f", f("S4_START"), f("S4_END"), f("SPEED4"), f("ANSWER_HOLD"), "email"),
    ("g", f("S5_START"), f("S5_END"), f("SPEED5"), f("QUERY_HOLD"), "email+zoom"),
]
durations = [clip_dur(s, e, sp, h) for _, s, e, sp, h, _ in clips]
total = sum(durations) - xfade * (len(clips) - 1)

# Output time when each clip becomes the visible one (after the incoming fade).
starts = []
t = 0.0
for n, d in enumerate(durations):
    starts.append(t)
    t = t + d - (xfade if n < len(clips) - 1 else 0.0)

def srt_time(seconds):
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

# Captions follow the clips so editing the ranges above retimes the words.
cap_specs = [
    (starts[0] + 0.35, starts[1] - 0.15, "LLMs state wrong numbers with total confidence."),
    (starts[2] + 0.20, starts[4] - 0.20, "Upload a CSV. Approve the schema."),
    (starts[4] + 0.20, starts[5] - 0.15, "Ask in plain English."),
    (starts[5] + 0.25, starts[6] - 0.15, "Every number is checked against the query results."),
    (starts[6] + 0.30, total - 3.50, "Click a number. See the exact SQL behind it."),
    (total - 3.30, total - 0.45, "Nexus. Live demo in comments."),
]
lines = []
for n, (a, b, text) in enumerate(cap_specs, start=1):
    lines.append(str(n))
    lines.append(f"{srt_time(a)} --> {srt_time(b)}")
    lines.append(text)
    lines.append("")
with open("captions.srt", "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(lines))

# Rounded red outline, transparent everywhere else.
hl = Image.new("RGBA", (crop_w, crop_h), (0, 0, 0, 0))
draw = ImageDraw.Draw(hl)
x, y, w, h = i("HL_X"), i("HL_Y"), i("HL_W"), i("HL_H")
draw.rounded_rectangle(
    [x, y, x + w, y + h],
    radius=i("HL_RADIUS"),
    outline=(192, 0, 0, 255),
    width=3,
)
hl.save(".build/highlight.png")

out_w, out_h = i("OUT_W"), i("OUT_H")
pad = os.environ["PAD_COLOR"]
fit = (
    f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease:flags=lanczos,"
    f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color={pad},setsar=1,format=yuv420p"
)
email = (
    f"drawbox=x={i('EMAIL_X')}:y={i('EMAIL_Y')}:w={i('EMAIL_W')}:h={i('EMAIL_H')}:"
    f"color={os.environ['EMAIL_COLOR']}:t=fill"
)
url = (
    f"drawbox=x={i('URL_X')}:y={i('URL_Y')}:w={i('URL_W')}:h={i('URL_H')}:"
    f"color=black:t=fill"
)

# Segment 5 zoom, eased in and back out. `on` is the frame index at FPS.
g_dur = durations[6]
zoom_out_at = g_dur - f("ZOOM_OUT_LEAD")
ease_frames = max(1, int(round(f("ZOOM_EASE") * fps)))
in_frame = int(round(f("ZOOM_IN_AT") * fps))
out_frame = int(round(zoom_out_at * fps))
out_frame2 = out_frame + ease_frames
cx = i("ZOOM_X") + i("ZOOM_W") / 2
cy = i("ZOOM_Y") + i("ZOOM_H") / 2
z_extra = f("ZOOM_MAX") - 1.0
# smoothstep(p) = p*p*(3-2*p), with p ramping across `ease_frames`.
ein = (
    f"if(lt(on\\,{in_frame})\\,0\\,"
    f"if(lt(on\\,{in_frame + ease_frames})\\,"
    f"((on-{in_frame})/{ease_frames})*((on-{in_frame})/{ease_frames})*(3-2*(on-{in_frame})/{ease_frames})\\,"
    f"1))"
)
eout = (
    f"if(lt(on\\,{out_frame})\\,0\\,"
    f"if(lt(on\\,{out_frame2})\\,"
    f"((on-{out_frame})/{ease_frames})*((on-{out_frame})/{ease_frames})*(3-2*(on-{out_frame})/{ease_frames})\\,"
    f"1))"
)
zexpr = f"1+{z_extra:.4f}*({ein})*(1-({eout}))"
xexpr = f"min(max({cx}-in_w/zoom/2\\,0)\\,in_w-in_w/zoom)"
yexpr = f"min(max({cy}-in_h/zoom/2\\,0)\\,in_h-in_h/zoom)"
zoom = (
    f"zoompan=z='{zexpr}':x='{xexpr}':y='{yexpr}':d=1:"
    f"s={crop_w}x{crop_h}:fps={fps}"
)
hl_enable = f"between(t\\,{f('HL_START'):.3f}\\,{f('HL_START') + f('HL_DUR'):.3f})"

chains = [f"[0:v]split={len(clips)}" + "".join(f"[s{n}]" for n in range(len(clips)))]
for idx, ((label, start, end, speed, hold, covers), dur) in enumerate(zip(clips, durations)):
    parts = [
        f"trim=start={start:.3f}:end={end:.3f}",
        f"setpts=(PTS-STARTPTS)/{speed:g}",
        f"fps={fps}",
    ]
    if hold > 0:
        parts.append(f"tpad=stop_mode=clone:stop_duration={hold:.3f}")
    parts.append(f"crop={crop_w}:{crop_h}:{i('CROP_X')}:{i('CROP_Y')}")
    if "url" in covers:
        parts.append(url)
    if "email" in covers:
        parts.append(email)
    if "zoom" in covers:
        chains.append(f"[s{idx}]" + ",".join(parts) + "[gbase]")
        chains.append(
            f"[gbase][2:v]overlay=0:0:enable='{hl_enable}',format=yuv420p,{zoom},{fit}[v{idx}]"
        )
        continue
    parts.append(fit)
    chains.append(f"[s{idx}]" + ",".join(parts) + f"[v{idx}]")

# Crossfades. Offset is on the running timeline.
nodes = []
prev = "v0"
acc = durations[0]
for k in range(1, len(clips)):
    offset = acc - xfade
    out = f"x{k}" if k < len(clips) - 1 else "vmix"
    nodes.append(
        f"[{prev}][v{k}]xfade=transition=fade:duration={xfade:.3f}:offset={offset:.3f}[{out}]"
    )
    prev = out
    acc = acc + durations[k] - xfade

# libass sizes SRT against PlayResY 288, then scales to the frame.
# 11 * (1350/288) is about 52px. Margins scale the same way.
style = (
    "Fontname=Arial\\,Bold=1\\,FontSize=11\\,PrimaryColour=&H00FFFFFF&\\,"
    "OutlineColour=&H00000000&\\,BorderStyle=1\\,Outline=1\\,Shadow=0\\,"
    "Alignment=2\\,MarginV=46\\,MarginL=20\\,MarginR=20"
)
end = (
    f"[vmix]fade=t=in:st=0:d={fade_in:.3f},"
    f"fade=t=out:st={total - fade_out:.3f}:d={fade_out:.3f},"
    f"subtitles=captions.srt:fontsdir='C\\:/Windows/Fonts':force_style='{style}'[vout]"
)

music_db = f("MUSIC_DB")
fin = f("MUSIC_FADE_IN")
fout = f("MUSIC_FADE_OUT")
audio = (
    f"[1:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,apad,atrim=0:{total:.3f},"
    f"volume={music_db:.1f}dB,"
    f"afade=t=in:st=0:d={fin:.3f},"
    f"afade=t=out:st={total - fout:.3f}:d={fout:.3f},"
    f"aformat=sample_rates=48000:channel_layouts=stereo[aout]"
)

graph = ";\n".join(chains + nodes + [end, audio]) + "\n"
with open(".build/filter.txt", "w", encoding="utf-8", newline="\n") as fh:
    fh.write(graph)
with open(".build/duration.txt", "w", encoding="utf-8", newline="\n") as fh:
    fh.write(f"{total:.3f}\n")
    for (label, *_rest), d, st in zip(clips, durations, starts):
        fh.write(f"{label} start={st:.3f} dur={d:.3f}\n")
print(f"duration {total:.3f}s")
for (label, *_rest), d, st in zip(clips, durations, starts):
    print(f"  {label}  out {st:6.2f}s  dur {d:5.2f}s")
PY

DURATION="$(cat .build/duration.txt | head -n 1)"
echo "Output length: ${DURATION}s (target 45-60)"
awk -v d="$DURATION" 'BEGIN { if (d < 45 || d > 60) print "WARNING: length is outside 45-60s. Adjust the ranges or holds at the top of build.sh." }'

echo
GRAPH="$(cat .build/filter.txt)"
echo "ffmpeg command:"
echo "ffmpeg -y -i \"$INPUT\" -i \"$MUSIC\" -i .build/highlight.png -filter_complex \"<\$(cat .build/filter.txt)>\" -map [vout] -map [aout] -c:v libx264 -preset medium -crf $CRF -pix_fmt yuv420p -r $FPS -c:a aac -b:a 160k -movflags +faststart \"$OUTPUT\""
echo

ffmpeg -y \
  -i "$INPUT" \
  -i "$MUSIC" \
  -i .build/highlight.png \
  -filter_complex "$GRAPH" \
  -map "[vout]" -map "[aout]" \
  -c:v libx264 -preset medium -crf "$CRF" \
  -pix_fmt yuv420p -r "$FPS" \
  -c:a aac -b:a 160k \
  -movflags +faststart \
  "$OUTPUT"

echo
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,avg_frame_rate,pix_fmt,sample_rate,channels -of default=noprint_wrappers=1 "$OUTPUT"
