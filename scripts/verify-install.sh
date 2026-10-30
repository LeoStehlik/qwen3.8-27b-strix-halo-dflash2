#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

(cd "$repo_dir/models" && sha256sum --check SHA256SUMS)
"$repo_dir/runtime/vulkan/llama-server" --version

for file in models.ini run-router.sh smoke-test.py; do
    if [[ ! -s "$repo_dir/$file" ]]; then
        printf 'Missing required file: %s\n' "$repo_dir/$file" >&2
        exit 1
    fi
done

printf 'Installation files verified.\n'
