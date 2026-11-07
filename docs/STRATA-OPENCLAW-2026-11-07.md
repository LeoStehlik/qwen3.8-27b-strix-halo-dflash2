# Flash-Next connected to OpenClaw — 2026-11-07

At the user's request, the existing `tiercelmoe` provider now serves Flash-Next
instead of the retired Qwen3.6 entry. The running OpenClaw gateway accepted the
config through hot reload; its PID remained 369. No gateway restart, Mac reboot,
default-agent model change or synthetic OpenClaw turn was performed.

Select it in a conversation with:

```text
/model qwen-flash-next
```

Full reference: `tiercelmoe/qwen3.8-flash-next-unsloth-ud-q4_k_xl`.
Private base URL: `http://100.96.8.54:8083/v1`.

## Connection and service

The Strata listener binds only the host's Tailscale IPv4 address, port 8083.
It uses the existing Tiercel provider credential; the credential is not included
in this repository. The local run config is mode 0600. No public/LAN wildcard
listener, proxy or Tailscale Serve rule was added.

The local Strata service was restarted to change its bind/auth configuration and
is now enabled at boot. Automatic restart after failure remains off during this
trial. The old 27B and Qwen3.6 units remain stopped and disabled; all their files
are retained. Boot operation for this new unit has not been tested. The model
settings and memory budget from the first-load record are unchanged.

The tracked base unit remains the loopback evaluation unit. The tracked
[`tailnet.conf.example`](../systemd/strata-flash-next.service.d/tailnet.conf.example)
shows the host's bind override; replace its address on another machine. Before
installing that override, set `host` to the private address and `api_key` to the
matching OpenClaw provider credential in the generated run config, and restrict
that file to mode 0600. Do not copy credentials into Git or shell history.

The host currently has the equivalent private bind directly in its user unit.
To reproduce using the tracked base unit plus override:

```bash
install -m 644 systemd/strata-flash-next.service ~/.config/systemd/user/
mkdir -p ~/.config/systemd/user/strata-flash-next.service.d
install -m 644 systemd/strata-flash-next.service.d/tailnet.conf.example \
  ~/.config/systemd/user/strata-flash-next.service.d/tailnet.conf
systemctl --user daemon-reload
systemctl --user enable strata-flash-next.service
systemctl --user restart strata-flash-next.service
```

## OpenClaw change

The provider keeps its `openai-completions` API, existing credential and 900-second
timeout. Its model list now contains the actual Flash-Next API model ID, native
context 262,144, text/image inputs, reasoning support and Qwen chat-template
thinking compatibility. The pre-existing 32,768 output-token setting is retained;
the small smoke-test limits were not installed as serving limits.

The old `qwen-moe-fast` model alias was replaced with `qwen-flash-next`.
Existing sampling settings were retained: temperature 0.3, top-p 0.95, top-k 20,
min-p 0.05, presence penalty 0 and repetition penalty 1. Thinking is enabled.
The old llama.cpp-specific `cache_prompt` extra body was removed; Strata manages
prefix reuse itself. Other providers and agent/session selections were not edited.

The [credential-free patch](../evidence/strata-2026-11-07/openclaw-provider.patch.json)
was schema-validated before application. OpenClaw requires explicit authorization
to replace an existing model array:

```bash
openclaw config patch --file tiercel-flash-next.patch.json \
  --replace-path models.providers.tiercelmoe.models --dry-run --json
openclaw config patch --file tiercel-flash-next.patch.json \
  --replace-path models.providers.tiercelmoe.models
openclaw models list --provider tiercelmoe --refresh --json
openclaw models list --agent francis --provider tiercelmoe --json
```

Hot reload applied at 13:36:51 UTC. The first catalog read still showed its cached
Qwen3.6 row; explicit catalog refresh published the Flash-Next row. Francis's live
catalog then reported it available with the new alias. Configuration on disk
alone was not treated as proof that the picker had updated.

## Validation and limits

From the Mac mini, using the provider credential over Tailscale:

- `/health` and `/v1/models` reported the loaded Flash-Next model and 256K context.
- A streamed chat completion returned exactly `READY`, normal stop, in 0.99 s.
- The gateway accepted the provider/alias hot reload without changing process.
- Francis's live gateway catalog reports the correct model available.

These checks supplement the earlier exact tool arguments and continuation test.
They do not establish real OpenClaw answer quality or cold 64K/128K throughput.
The user supplies the real agent requests. Long-context benchmarks, disk state
restore, image inference and broader startup reliability remain pending.

Public evidence: [network and reload](../evidence/strata-2026-11-07/openclaw-network-and-reload.json),
[Francis model catalog](../evidence/strata-2026-11-07/openclaw-francis-catalog.json).
