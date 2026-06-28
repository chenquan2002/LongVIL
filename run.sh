#!/usr/bin/env bash
set -euo pipefail


cd "$(dirname "$0")"


data_json=./data/example/example1/example.json
data_type=clean


if [[ $# -ge 1 ]]; then
  data_json="$1"
fi
if [[ $# -ge 2 ]]; then
  data_type="$2"
fi


dir_path="$(dirname "$data_json")"
filename="$(basename "$data_json" .json)"

frame_path="${dir_path}/${filename}"
output="./output_new"


echo "data_json: $data_json"
echo "frame_path: $frame_path"
echo "output: $output"
echo "data_type: $data_type"

python run.py \
    --engine_type gpt \
    --api_key "${LONGVIL_API_KEY:-YOUR_API_KEY}" \
    --base_url "${LONGVIL_API_BASE_URL:-https://your_baseurl/v1/chat/completions}" \
    --model_name gpt-4o \
    --llm_model_name gpt-4o \
    --frame_path "$frame_path" \
    --output "$output" \
    --data_json "$data_json" \
    --data_type "$data_type" \
    --use_reflection y
