#!/usr/bin/env bash
# 把普通 SDR 视频转成"超亮"的 HLG HDR 视频（10-bit HEVC），不需要 ComfyUI。
# 用法: scripts/hdr_hlg.sh input.mp4 [output.mp4] [extra|standard]
set -euo pipefail
IN="${1:?用法: hdr_hlg.sh input.mp4 [output.mp4] [extra|standard]}"
OUT="${2:-${IN%.*}_HDR.mp4}"
LEVEL="${3:-extra}"

if [ "$LEVEL" = "standard" ]; then
  CURVE="0/0 0.25/0.25 0.5/0.6 0.75/0.88 0.9/0.98 1/1"      # 标准亮
else
  CURVE="0/0 0.1/0.13 0.25/0.36 0.5/0.7 0.75/0.92 0.9/0.99 1/1"   # 特别亮
fi

ffmpeg -i "$IN" \
  -vf "scale=in_range=tv:in_color_matrix=bt709,format=gbrp16le,curves=all='${CURVE}',scale=out_color_matrix=bt2020:out_range=tv,format=yuv420p10le,setparams=range=tv:color_primaries=bt2020:color_trc=arib-std-b67:colorspace=bt2020nc" \
  -c:v libx265 -preset fast -crf 16 -tag:v hvc1 \
  -color_primaries bt2020 -color_trc arib-std-b67 -colorspace bt2020nc -color_range tv \
  -x265-params "colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc:range=limited:atc-sei=18" \
  -c:a copy "$OUT"

echo "完成: $OUT"
