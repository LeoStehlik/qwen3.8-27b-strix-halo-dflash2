#!/usr/bin/env bash
set -euo pipefail

base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$base"
target="${QWEN_TARGET_MODEL:-$base/models/Qwen3.8-27B-UD-Q4_K_XL.gguf}"
model_alias="${QWEN_MODEL_ALIAS:-qwen3.8-27b-ud-q4-xl-dflash2}"
draft="$base/models/Qwen3.8-27B-DFlash2-Q4_K_M.gguf"
projector="$base/models/mmproj-F16.gguf"

for model in "$target" "$draft" "$projector"; do
    if [[ ! -s "$model" ]]; then
        printf 'Missing model: %s\n' "$model" >&2
        exit 1
    fi
done

# Invoke the top-level portable launcher, not bin/llama-server. It selects the
# bundled Mesa/RADV driver and enables the Strix Halo Vulkan tuning defaults.
exec "$base/runtime/vulkan/llama-server" \
    --model "$target" \
    --mmproj "$projector" \
    --mmproj-offload \
    --image-min-tokens 1024 \
    --alias "$model_alias" \
    --n-gpu-layers all \
    --flash-attn on \
    --ctx-size 245760 \
    --parallel 1 \
    --batch-size 2048 \
    --ubatch-size 2048 \
    --cache-type-k q8_0 \
    --cache-type-v q8_0 \
    --threads 16 \
    --threads-batch 16 \
    --spec-draft-model "$draft" \
    --spec-type draft-dflash \
    --spec-draft-n-max 4 \
    --spec-draft-n-min 0 \
    --spec-draft-ngl all \
    --jinja \
    --reasoning auto \
    --reasoning-preserve \
    --reasoning-format deepseek \
    --host 127.0.0.1 \
    --port 8080 \
    --cors-origins localhost \
    --no-cors-credentials \
    --metrics \
    --log-timestamps
