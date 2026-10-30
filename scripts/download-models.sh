#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
models_dir="$repo_dir/models"
checksums="$models_dir/SHA256SUMS"

unsloth_repo=unsloth/Qwen3.8-27B-GGUF
unsloth_rev=4ca720788d1e01f1bff70c033e0d0028fd02e502
draft_repo=incoai/Qwen3.8-27B-DFlash2-GGUF
draft_rev=144eb06583b4fb0b6e54bc814b16a206a240f4d2

if ! command -v hf >/dev/null 2>&1; then
    printf 'The Hugging Face CLI is required. Install it with:\n' >&2
    printf '  python3 -m pip install --user huggingface_hub\n' >&2
    exit 1
fi

mkdir -p "$models_dir"

download_if_needed() {
    local repo=$1
    local revision=$2
    local filename=$3
    local expected
    local actual

    expected=$(awk -v name="$filename" '$2 == name { print $1 }' "$checksums")
    if [[ -z "$expected" ]]; then
        printf 'No checksum recorded for %s\n' "$filename" >&2
        exit 1
    fi

    if [[ -f "$models_dir/$filename" ]]; then
        actual=$(sha256sum "$models_dir/$filename" | cut -d' ' -f1)
        if [[ "$actual" == "$expected" ]]; then
            printf 'Already verified: %s\n' "$filename"
            return
        fi
        printf 'Existing model has unexpected SHA-256: %s\n' "$models_dir/$filename" >&2
        exit 1
    fi

    hf download "$repo" "$filename" \
        --revision "$revision" \
        --local-dir "$models_dir"

    actual=$(sha256sum "$models_dir/$filename" | cut -d' ' -f1)
    if [[ "$actual" != "$expected" ]]; then
        printf 'Model SHA-256 mismatch for %s\n' "$filename" >&2
        exit 1
    fi
}

download_if_needed "$unsloth_repo" "$unsloth_rev" Qwen3.8-27B-UD-Q4_K_XL.gguf
download_if_needed "$unsloth_repo" "$unsloth_rev" Qwen3.8-27B-UD-Q5_K_XL.gguf
download_if_needed "$unsloth_repo" "$unsloth_rev" mmproj-F16.gguf
download_if_needed "$draft_repo" "$draft_rev" Qwen3.8-27B-DFlash2-Q4_K_M.gguf

(cd "$models_dir" && sha256sum --check SHA256SUMS)
