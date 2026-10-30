#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
template="$repo_dir/systemd/qwen38-dflash2.service.in"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
unit="$unit_dir/qwen38-dflash2.service"

mkdir -p "$unit_dir"
escaped_repo=${repo_dir//\\/\\\\}
escaped_repo=${escaped_repo//&/\\&}
escaped_repo=${escaped_repo//|/\\|}
sed "s|@REPO_DIR@|$escaped_repo|g" "$template" > "$unit"

systemctl --user daemon-reload
systemctl --user enable --now qwen38-dflash2.service

printf 'Installed %s\n' "$unit"
printf 'For service startup without an interactive login, run once:\n'
printf '  sudo loginctl enable-linger %s\n' "$USER"
