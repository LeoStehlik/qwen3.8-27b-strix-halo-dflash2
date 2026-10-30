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
# The router is private; the public endpoint is a streaming single-flight
# proxy that collapses concurrent byte-identical inference requests.
backend_host=127.0.0.1
backend_port=${QWEN_BACKEND_PORT:-8081}
public_host=${QWEN_BIND_HOST:-127.0.0.1}
public_port=${QWEN_PUBLIC_PORT:-8080}

backend_pid=
proxy_pid=

cleanup() {
    trap - EXIT INT TERM
    [[ -z "$proxy_pid" ]] || kill -TERM "$proxy_pid" 2>/dev/null || true
    [[ -z "$backend_pid" ]] || kill -INT "$backend_pid" 2>/dev/null || true
    [[ -z "$proxy_pid" ]] || wait "$proxy_pid" 2>/dev/null || true
    [[ -z "$backend_pid" ]] || wait "$backend_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$base/runtime/vulkan/llama-server" \
    --models-preset "$base/models.ini" \
    --models-max 1 \
    --models-autoload \
    --host "$backend_host" \
    --port "$backend_port" \
    --cors-origins localhost \
    --no-cors-credentials \
    --metrics \
    --log-timestamps &
backend_pid=$!

ready=0
for _ in $(seq 1 120); do
    if curl --silent --fail --max-time 1 "http://${backend_host}:${backend_port}/health" >/dev/null; then
        ready=1
        break
    fi
    if ! kill -0 "$backend_pid" 2>/dev/null; then
        wait "$backend_pid"
        exit $?
    fi
    sleep 0.5
done

if [[ "$ready" -ne 1 ]]; then
    printf 'Router did not become healthy within 60 seconds\n' >&2
    exit 1
fi

COALESCE_LISTEN_HOST="$public_host" \
COALESCE_LISTEN_PORT="$public_port" \
COALESCE_UPSTREAM_HOST="$backend_host" \
COALESCE_UPSTREAM_PORT="$backend_port" \
    python3 "$base/coalescing-proxy.py" &
proxy_pid=$!

wait -n "$backend_pid" "$proxy_pid"
status=$?
exit "$status"
