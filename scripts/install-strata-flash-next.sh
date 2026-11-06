#!/usr/bin/env bash
# Acquire the pinned packaged engine and model. Does not start or stop any server.
set -euo pipefail

feed=https://github.com/Niko1221/Strata/releases/download/v0.2.11
strata_bin=${STRATA_BIN:-$HOME/.local/bin/strata}
model_dir=${STRATA_MODEL_DIR:-$HOME/models/strata-flash-next}
install_dir=${STRATA_INSTALL_DIR:-$HOME/.local/share/strata/flash-next}
export STRATA_INSTALL_DIR="$install_dir"
export STRATA_DL_CONNECTIONS=${STRATA_DL_CONNECTIONS:-16}

if [[ ! -x "$strata_bin" ]]; then
    installer=$(mktemp)
    trap 'rm -f "$installer"' EXIT
    curl --fail --location --retry 3 "$feed/install.sh" -o "$installer"
    STRATA_FEED="$feed" sh "$installer"
fi
"$strata_bin" update --feed "$feed" --backend hip-halo --yes
"$strata_bin" install -- \
    --family unsloth --model UD-Q4_K_XL --source huggingface \
    --context 262144 --kv int8 --vision gpu --parallel 1 --mtp on \
    --backend hip --host 127.0.0.1 --port 8083 \
    --data-dir "$model_dir" --feed "$feed" --yes --no-start
"$strata_bin" components engine --backend hip --full --output json
printf '\nPrepared only. Review the generated config in %s before starting.\n' "$install_dir"
