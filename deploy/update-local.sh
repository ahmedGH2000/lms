#!/usr/bin/env bash
# Run the copy from the NEW extracted release and pass the EXISTING project path.
set -Eeuo pipefail
release_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
target_dir="${1:?Usage: bash /path/to/new/nightjar-learning/deploy/update-local.sh /path/to/existing/nightjar-learning}"
target_dir="$(cd -- "$target_dir" && pwd -P)"
[[ "$release_dir" != "$target_dir" ]] || { echo 'Extract the new release separately; do not overwrite the existing project first.' >&2; exit 1; }
[[ -f "$target_dir/deploy/.env" && -f "$target_dir/deploy/compose.yaml" ]] || { echo 'Target is not an existing Nightjar installation with deploy/.env.' >&2; exit 1; }
python3 "$release_dir/deploy/verify_release.py" "$release_dir"
cd -- "$target_dir"
compose=(docker compose --env-file deploy/.env -f deploy/compose.yaml)
# Inspect only command/mount metadata; never print resolved environment secrets.
"${compose[@]}" config --format json | python3 -c '
import json,sys,pathlib
c=json.load(sys.stdin)["services"]["app"]
if c.get("command") != ["bash", "/workspace/deploy/init.sh"]:
    raise SystemExit("The app startup command differs from the supported bootstrap. Review deploy/compose.yaml before updating.")
mount=next((v for v in c.get("volumes",[]) if v.get("target")=="/workspace"),{})
if mount.get("type")!="bind" or pathlib.Path(mount.get("source", "")).resolve()!=pathlib.Path.cwd():
    raise SystemExit("Compose does not mount this project at /workspace. Update the actual mounted project instead.")
'
echo 'Backing up the existing database and uploaded files. App must be running.'
"${compose[@]}" exec -T app /home/frappe/work/bench/env/bin/python - < "$release_dir/deploy/backup_local.py"
backup_dir="$(mktemp -d "${target_dir}-before-update-XXXXXXXX")"
# Export the site backups before stopping, so the backup also lives outside the volume.
"${compose[@]}" cp app:/home/frappe/work/bench/sites/nightjar.localhost/private/backups "$backup_dir/site-backups"
echo "Backup directory: $backup_dir"
"${compose[@]}" stop app
trap 'echo "Update stopped. Data and .env were retained. Source/site backups: $backup_dir. Inspect the reported error; do not delete volumes." >&2' ERR
python3 - "$release_dir" "$target_dir" "$backup_dir" <<'UPDATE_SOURCE'
from pathlib import Path
import json, shutil, sys
source, target, backup = map(Path, sys.argv[1:])
manifest = json.loads((source/'release-manifest.json').read_text())
names = set(manifest['files']) | {'release-manifest.json', 'README.md', 'LICENSE', 'THIRD-PARTY-NOTICES.md'}
for folder in ('docs','tests','licenses'):
    names.update(str(p.relative_to(source)) for p in (source/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
for name in sorted(names):
    # Existing environment, ports, images and storage mapping remain authoritative.
    if name in {'deploy/compose.yaml', 'deploy/.env', 'deploy/.env.example'}:
        continue
    src, dst = source/name, target/name
    if not dst.resolve().is_relative_to(target.resolve()):
        raise SystemExit('Refusing to write through a path outside the project: '+name)
    if dst.is_file():
        saved = backup/'source'/name
        saved.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(dst,saved)
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)
UPDATE_SOURCE
# Verify matching app sources; Compose/environment are intentionally user-owned.
python3 "$target_dir/deploy/verify_release.py" "$target_dir"
"${compose[@]}" up -d --no-deps --force-recreate app
echo 'Update started. Follow logs until the verified release and Starting development services messages:'
echo 'docker compose --env-file deploy/.env -f deploy/compose.yaml logs -f app'
