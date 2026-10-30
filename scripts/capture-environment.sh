#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

printf 'date_utc: '
date --utc --iso-8601=seconds

if [[ -r /etc/os-release ]]; then
    . /etc/os-release
    printf 'os: %s\n' "${PRETTY_NAME:-unknown}"
fi

printf 'kernel: '
uname -r
lscpu | grep -E '^(Model name|CPU\(s\)|Core\(s\) per socket|Thread\(s\) per core):'
free -h | sed -n '1,2p'
lspci -nn | grep -Ei 'VGA|Display' || true

if command -v vulkaninfo >/dev/null 2>&1; then
    vulkaninfo --summary 2>/dev/null | grep -E 'deviceName|driverName|driverInfo' || true
fi

if [[ -x "$repo_dir/runtime/vulkan/llama-server" ]]; then
    "$repo_dir/runtime/vulkan/llama-server" --version
fi

if [[ -f "$repo_dir/models/SHA256SUMS" ]]; then
    printf 'model checksum manifest:\n'
    sed 's/^/  /' "$repo_dir/models/SHA256SUMS"
fi

for file in /sys/class/drm/card*/device/power_dpm_force_performance_level; do
    if [[ -r "$file" ]]; then
        printf '%s: ' "$file"
        cat "$file"
    fi
done
