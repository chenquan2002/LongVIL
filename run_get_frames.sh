set -euo pipefail

video_path="/home/chenquan/LongVIL/data/example/example/example_complex.mp4"

cd "$(dirname "$0")"

out_dir="$(dirname "$video_path")"

python3 get_frames.py \
  --video_path "$video_path" \
  --output_dir "$out_dir" \
  --gaussian_sigma 5 \
  --prominence 0.8

echo "output dir：$out_dir/$(basename "${video_path%.*}")"
