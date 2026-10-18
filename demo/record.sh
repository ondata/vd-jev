#!/usr/bin/env bash
# Record the README demo. VHS records at 2x (3000x1120, font 30) into an MP4: a GIF that size
# needs more than 11 GB of RAM for its palette, and VHS GIFs are mostly 1x1 delta frames that
# some viewers (XnView) refuse. ffmpeg then makes the GIF at 1500 px wide, 10 fps, one
# 256-colour palette. The 2x MP4 stays in tmp/ and is the source for other videos.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p tmp
vhs demo/demo.tape
ffmpeg -v error -y -i tmp/demo-vhs.mp4 \
  -vf "fps=10,scale=1500:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=none" demo/demo.gif
ls -l demo/demo.gif
