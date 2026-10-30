#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
runtime_dir="$repo_dir/runtime"
archive="$runtime_dir/strix-halo-llamacpp-vulkan-portable.tar.gz"
url=https://github.com/Nathanw1014/strix-halo-llamacpp/releases/download/v0.8.0/strix-halo-llamacpp-vulkan-portable.tar.gz
expected=2332fb0947bb1570f0f16ad84ede1772d4aa0cd0446133d434ab7653b7cc3d28

mkdir -p "$runtime_dir"

if [[ -f "$archive" ]]; then
    actual=$(sha256sum "$archive" | cut -d' ' -f1)
    if [[ "$actual" != "$expected" ]]; then
        printf 'Existing archive has unexpected SHA-256: %s\n' "$archive" >&2
        printf 'Expected %s, got %s\n' "$expected" "$actual" >&2
        exit 1
    fi
else
    partial="$archive.part"
    curl --fail --location --continue-at - --output "$partial" "$url"
    actual=$(sha256sum "$partial" | cut -d' ' -f1)
    if [[ "$actual" != "$expected" ]]; then
        printf 'Runtime SHA-256 mismatch: expected %s, got %s\n' "$expected" "$actual" >&2
        exit 1
    fi
    mv "$partial" "$archive"
fi

tar -xzf "$archive" -C "$runtime_dir"
"$runtime_dir/vulkan/llama-server" --version
