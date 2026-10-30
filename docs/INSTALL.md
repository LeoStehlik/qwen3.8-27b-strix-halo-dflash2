# Installation cookbook

This guide reproduces the reference deployment without committing model or
runtime binaries to Git.

## 1. Reference platform

The tested machine is:

- AMD Ryzen AI Max+ 395, 16 cores / 32 threads
- Radeon 8060S integrated GPU (`gfx1151`, PCI ID `1002:1586`)
- 128 GB installed unified memory, approximately 115 GiB visible to Linux
- Ubuntu 26.04.1 LTS, kernel 7.0.0
- Host RADV Mesa 26.0.8

The portable runtime bundles its own validated RADV Mesa 26.2.4 libraries, so
the host Mesa version is not the backend actually used by the launcher.

This exact runtime bundle is specific to Linux x86-64 and AMD Strix Halo. The
configuration may be useful elsewhere, but the supplied binary is not a
general-purpose package.

## 2. Host prerequisites

Install the basic tools and Vulkan loader using the package manager appropriate
for the distribution. On Ubuntu, the required package names normally include:

```bash
sudo apt install curl git python3 python3-venv libvulkan1
```

Confirm that the GPU is visible:

```bash
ls -l /dev/dri
vulkaninfo --summary
```

Install the Hugging Face CLI in a virtual environment if it is not already
available:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade huggingface_hub
hf --help
```

The listed model repositories are public at the time of writing. If Hugging
Face changes their access requirements, authenticate with `hf auth login`.
Never commit the resulting token.

## 3. Download the pinned runtime

```bash
./scripts/download-runtime.sh
```

The script downloads:

```text
Nathanw1014/strix-halo-llamacpp release v0.8.0
strix-halo-llamacpp-vulkan-portable.tar.gz
SHA-256 2332fb0947bb1570f0f16ad84ede1772d4aa0cd0446133d434ab7653b7cc3d28
```

The runtime identifies itself as llama.cpp build 11001, source commit
`629d2f7b45285e3f7556648c50c167159c532476`.

Always invoke `runtime/vulkan/llama-server`, not the binary below `bin/`
directly. The top-level launcher selects the bundled RADV driver and applies
the package's Strix Halo environment defaults.

## 4. Download the pinned models

```bash
./scripts/download-models.sh
```

The script downloads these exact revisions:

| Role | Hugging Face source | Revision | File |
|---|---|---|---|
| Q4 target | `unsloth/Qwen3.8-27B-GGUF` | `4ca720788d1e01f1bff70c033e0d0028fd02e502` | `Qwen3.8-27B-UD-Q4_K_XL.gguf` |
| Q5 target | same | same | `Qwen3.8-27B-UD-Q5_K_XL.gguf` |
| Vision projector | same | same | `mmproj-F16.gguf` |
| DFlash2 drafter | `incoai/Qwen3.8-27B-DFlash2-GGUF` | `144eb06583b4fb0b6e54bc814b16a206a240f4d2` | `Qwen3.8-27B-DFlash2-Q4_K_M.gguf` |

Verification is mandatory:

```bash
cd models
sha256sum --check SHA256SUMS
```

Expected sizes and hashes:

| File | Bytes | SHA-256 |
|---|---:|---|
| Q4 target | 17,559,178,144 | `3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e` |
| Q5 target | 20,876,938,144 | `8601193d3d5760c37fb8ce1b43afebc69df5fb24e1fbc5a547c32e2200305276` |
| DFlash2 Q4_K_M | 1,143,006,816 | `d169ad335929adc0d77e10e2523f968f3e75f547637ad739b0a137ccde111b5f` |
| F16 projector | 927,607,488 | `cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e` |

The similarly named z-lab DFlash2 GGUF has a different SHA-256. This deployment
was tested with the `incoai` artifact above; do not treat same-sized files as
identical.

## 5. Validate before starting

```bash
./scripts/verify-install.sh
```

For a foreground run:

```bash
./run-router.sh
```

From another terminal:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/v1/models
curl http://127.0.0.1:8080/coalescer/metrics
```

## 6. Install the user service

```bash
./scripts/install-service.sh
sudo loginctl enable-linger "$USER"
```

The installer renders the current repository path into
`~/.config/systemd/user/qwen38-dflash2.service`, reloads the user manager, and
enables the service.

The public proxy binds to localhost by default. To expose it only on a
Tailscale address, create `~/.config/qwen38-dflash2.env` and restart:

```bash
QWEN_BIND_HOST=100.x.y.z
```

The model router remains private on `127.0.0.1:8081`. The optional
`QWEN_PUBLIC_PORT` and `QWEN_BACKEND_PORT` variables override the default
ports.

Useful commands:

```bash
systemctl --user status qwen38-dflash2
systemctl --user restart qwen38-dflash2
systemctl --user stop qwen38-dflash2
journalctl --user -u qwen38-dflash2 -f
```

## 7. Validate text, routing and vision

```bash
./smoke-test.py qwen3.8-27b-q4-fast
./smoke-test.py qwen3.8-27b-q5-quality
./smoke-test.py qwen3.8-27b-q4-fast

./make-vision-card.py
./smoke-test.py qwen3.8-27b-q4-fast --image vision-test-card.bmp
```

The Q4 to Q5 to Q4 sequence verifies on-demand loading and eviction. A model
switch includes a cold-load delay and discards the evicted model's live KV
state; the client must resend conversation history, as normal for a stateless
OpenAI-compatible API.

## 8. Direct API request

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3.8-27b-q4-fast",
    "messages": [{"role": "user", "content": "Explain speculative decoding."}],
    "temperature": 0.2,
    "top_p": 0.95,
    "top_k": 20,
    "min_p": 0.0,
    "max_tokens": 256
  }'
```

The service intentionally listens only on localhost and has no API
authentication. Read [SECURITY.md](../SECURITY.md) before changing the bind
address.
