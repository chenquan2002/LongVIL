
set -euo pipefail


cd "$(dirname "$0")"


data_json=./data/example/example/example.json
data_type=clean  


if [[ $# -ge 1 ]]; then
  data_json="$1"
fi


dir_path="$(dirname "$data_json")"
filename="$(basename "$data_json" .json)"

frame_path="${dir_path}/${filename}"
output="./output"


echo "data_json: $data_json"
echo "frame_path: $frame_path"
echo "output: $output"
echo "data_type: $data_type"

python run.py \
    --engine_type gpt \
    --api_key your_key \
    --model_name gpt-4o \
    --llm_model_name gpt-4o \
    --frame_path "$frame_path" \
    --output "$output" \
    --data_json "$data_json" \
    --data_type "$data_type" \
    --use_reflection y
