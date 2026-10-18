#!/usr/bin/env bash
# Record the README demo: VHS writes a GIF of mostly 1x1 delta frames, which some viewers
# (XnView) refuse; ffmpeg re-encodes it at 10 fps with one palette.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p tmp
vhs demo/demo.tape
ffmpeg -v error -y -i tmp/demo-vhs.gif \
  -vf "fps=10,split[a][b];[a]palettegen=max_colors=64[p];[b][p]paletteuse=dither=none" demo/demo.gif
ls -l demo/demo.gif
