#!/usr/bin/env bash
# Start an isolated evaluation listener after freeing the GPU of other models.
set -euo pipefail
strata_bin=${STRATA_BIN:-$HOME/.local/bin/strata}
export STRATA_INSTALL_DIR=${STRATA_INSTALL_DIR:-$HOME/.local/share/strata/flash-next}
exec "$strata_bin" launch \
    --family unsloth --model UD-Q4_K_XL \
    --data-dir "${STRATA_MODEL_DIR:-$HOME/models/strata-flash-next}" \
    --context 256k --kv int8 --vision gpu --parallel 1 --drafting mtp \
    --set spec=4 --set prefill=16384 --set STRATA_ROUTE_TAIL_SKIP=0 \
    --access local --port 8083 --save-preset flash-next-halo \
    --feed https://github.com/Niko1221/Strata/releases/download/v0.2.11 \
    --tune skip --no-tui --yes "$@"
