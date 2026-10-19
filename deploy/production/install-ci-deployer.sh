#!/usr/bin/env bash
set -Eeuo pipefail

public_key_file="${1:?Usage: sudo bash install-ci-deployer.sh /path/to/deploy-key.pub}"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

[[ "$(id -u)" -eq 0 ]] || { echo 'Run this installer with sudo.' >&2; exit 1; }
[[ -f "$public_key_file" ]] || { echo 'Deployment public key was not found.' >&2; exit 1; }
key="$(<"$public_key_file")"
[[ "$key" == ssh-ed25519\ * ]] || { echo 'Use an Ed25519 public key.' >&2; exit 1; }
[[ -f /opt/nightjar-learning/app/deploy/production/.env ]] || {
  echo 'Existing Nightjar production environment was not found.' >&2
  exit 1
}

if ! id nightjar-deploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash nightjar-deploy
fi

install -o root -g root -m 0755 "$script_dir/nightjar-deploy" /usr/local/sbin/nightjar-deploy
install -o root -g root -m 0755 "$script_dir/nightjar-ssh-entry" /usr/local/sbin/nightjar-ssh-entry

install -d -m 700 -o nightjar-deploy -g nightjar-deploy /home/nightjar-deploy/.ssh
printf 'restrict,command="/usr/local/sbin/nightjar-ssh-entry" %s\n' "$key" \
  > /home/nightjar-deploy/.ssh/authorized_keys
chown nightjar-deploy:nightjar-deploy /home/nightjar-deploy/.ssh/authorized_keys
chmod 600 /home/nightjar-deploy/.ssh/authorized_keys

cat > /etc/sudoers.d/nightjar-deploy <<'SUDOERS'
nightjar-deploy ALL=(root) NOPASSWD: /usr/local/sbin/nightjar-deploy *
SUDOERS
chmod 0440 /etc/sudoers.d/nightjar-deploy
visudo -cf /etc/sudoers.d/nightjar-deploy >/dev/null

echo 'Restricted Nightjar deployment account installed.'
