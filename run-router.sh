#!/usr/bin/env bash
set -euo pipefail

base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$base"

required=(
    "models/Qwen3.8-27B-UD-Q4_K_XL.gguf"
    "models/Qwen3.8-27B-UD-Q5_K_XL.gguf"
    "models/Qwen3.8-27B-DFlash2-Q4_K_M.gguf"
    "models/mmproj-F16.gguf"
)

for model in "${required[@]}"; do
    if [[ ! -s "$model" ]]; then
        printf 'Missing model: %s\n' "$model" >&2
        exit 1
    fi
done

# models-max=1 keeps one 27B target resident. Requests select the fast or
# quality preset using the OpenAI API's `model` field; the router swaps models.
exec "$base/runtime/vulkan/llama-server" \
    --models-preset "$base/models.ini" \
    --models-max 1 \
    --models-autoload \
    --host 127.0.0.1 \
    --port 8080 \
    --cors-origins localhost \
    --no-cors-credentials \
    --metrics \
    --log-timestamps
