#!/usr/bin/env bash
set -Eeuo pipefail

umask 0002
assets_path=/home/frappe/frappe-bench/sites/assets
baked_path=/home/frappe/frappe-bench/assets

rm -rf "$assets_path"
mkdir -p "$(dirname "$assets_path")"
ln -s "$baked_path" "$assets_path"

exec "$@"

