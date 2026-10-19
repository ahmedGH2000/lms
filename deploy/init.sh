#!/usr/bin/env bash
set -Eeuo pipefail
stage="preflight"
trap 'echo "Nightjar setup failed during: $stage (line $LINENO). Existing data has been retained; inspect the error above." >&2' ERR
export CYPRESS_INSTALL_BINARY=0
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=6144}"
export PATH="${NVM_DIR:-/home/frappe/.nvm}/versions/node/v${NODE_VERSION_DEVELOP:-22}/bin:$PATH"

phase() { stage="$1"; printf '\n[Nightjar] %s\n' "$stage"; }

# Bench may write apps.txt WITHOUT a trailing newline. Never append with echo.
# Repair only the exact concatenations produced by the previous bootstrap.
register_apps() {
  env/bin/python - "$@" <<'REGISTER_APPS'
from pathlib import Path
import os
import shutil
import sys
import tempfile

path = Path('sites/apps.txt')
old = path.read_text() if path.exists() else ''
apps = []
repaired = False
for line in old.splitlines():
    name = line.strip()
    if not name:
        continue
    for upstream in ('frappe', 'payments', 'lms'):
        if name == upstream + 'nightjar_learning':
            apps.extend((upstream, 'nightjar_learning'))
            repaired = True
            break
    else:
        apps.append(name)
apps = list(dict.fromkeys([*apps, *sys.argv[1:]]))
new = '\n'.join(apps) + '\n'
if new != old:
    if repaired:
        backup = path.with_name('apps.txt.before-nightjar-repair')
        if not backup.exists():
            shutil.copy2(path, backup)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        f.write(new)
        f.flush()
        os.fsync(f.fileno())
    temporary.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o644)
    temporary.replace(path)
if repaired:
    print('Repaired merged app names; original saved as sites/apps.txt.before-nightjar-repair')
REGISTER_APPS
}

# Fetch pins before installation. Preserve only known generated lockfile changes
# from earlier bootstrap attempts; never reset or clean application source.
pin_revision() {
  local repo="$1" url="$2" revision="$3" path
  local -a generated=()
  if [[ "$(git -C "$repo" rev-parse HEAD)" == "$revision" ]]; then
    return
  fi
  if ! git -C "$repo" cat-file -e "${revision}^{commit}" 2>/dev/null; then
    git -C "$repo" fetch --no-tags --depth=1 "$url" "$revision"
  fi
  while IFS= read -r -d '' path; do
    case "$path" in
      yarn.lock|frontend/yarn.lock) generated+=("$path") ;;
      *) echo "Refusing to switch $repo: source file $path has local changes. Preserve/review them first." >&2; return 1 ;;
    esac
  done < <(git -C "$repo" diff --name-only -z HEAD --)
  if [[ ${#generated[@]} -gt 0 ]]; then
    git -C "$repo" -c user.name='Nightjar bootstrap' -c user.email='bootstrap@localhost' \
      stash push --message "Nightjar: preserve generated lockfiles before $revision" -- "${generated[@]}"
    echo "Saved generated lockfile changes in $repo Git stash."
  fi
  git -C "$repo" checkout --detach "$revision"
}

site="${SITE_NAME:-nightjar.localhost}"
: "${DB_ROOT_PASSWORD:?Set DB_ROOT_PASSWORD in deploy/.env}"
: "${ADMIN_PASSWORD:?Set ADMIN_PASSWORD in deploy/.env}"
: "${NIGHTJAR_VIDEO_SECRET:?Set NIGHTJAR_VIDEO_SECRET in deploy/.env}"
phase "Checking development tools"
python3 /workspace/deploy/verify_release.py /workspace
for tool in bench git node yarn npm; do command -v "$tool" >/dev/null; done
node -e 'if (Number(process.versions.node.split(".")[0]) < 22) { console.error("This LMS revision requires Node.js 22 or newer."); process.exit(1); }'
node --version
yarn --version
phase "Preparing Bench"
if [[ ! -d bench/apps/frappe ]]; then
  bench init --frappe-branch version-15 --skip-assets --skip-redis-config-generation bench
fi
cd bench
[[ -x env/bin/python && -f sites/apps.txt && -f Procfile ]] || {
  echo "Bench initialization is incomplete. Preserve this volume and inspect its setup log before retrying." >&2
  exit 1
}
phase "Repairing app registry"
register_apps
if [[ ! -f .nightjar-dependencies ]]; then
  phase "Installing pinned upstream dependencies"
  pin_revision apps/frappe https://github.com/frappe/frappe.git b0b5b99a1d9d2cb3d54b32293d3854bf2c15f4a4
  bench set-mariadb-host db
  bench set-redis-cache-host redis://redis:6379
  bench set-redis-queue-host redis://redis:6379
  bench set-redis-socketio-host redis://redis:6379
  sed -i '/redis/d; /watch/d' Procfile
  [[ -d apps/payments ]] || git clone --branch version-15 --depth=1 --origin upstream https://github.com/frappe/payments.git apps/payments
  pin_revision apps/payments https://github.com/frappe/payments.git 9885a6e500104f1f160add47d55b370773e67a81
  [[ -d apps/lms ]] || git clone --branch version-15 --depth=1 --origin upstream https://github.com/frappe/lms.git apps/lms
  pin_revision apps/lms https://github.com/frappe/lms.git 87168fc7b2f24559e474ea4702cf1aa63b0db4e8
  bench setup requirements frappe payments lms
  touch .nightjar-dependencies
fi
phase "Applying reviewed compatibility fixes"
env/bin/python /workspace/deploy/apply_upstream_patches.py "$PWD"
phase "Installing Nightjar source"
mkdir -p apps/nightjar_learning
env/bin/python - <<'COPY_SOURCE'
import shutil
shutil.copytree('/workspace', 'apps/nightjar_learning', dirs_exist_ok=True,
    ignore=shutil.ignore_patterns('node_modules', '.env', 'private-media', '.git', '__pycache__', '.pytest_cache'))
COPY_SOURCE
env/bin/pip install -e apps/nightjar_learning
env/bin/python /workspace/deploy/verify_release.py "$PWD/apps/nightjar_learning" --imports
register_apps frappe payments lms nightjar_learning
phase "Checking application imports"
env/bin/python - <<'CHECK_APPS'
import importlib
from pathlib import Path
for name in Path('sites/apps.txt').read_text().splitlines():
    app = importlib.import_module(name)
    modules = Path(app.__file__).with_name('modules.txt')
    if not modules.is_file():
        raise SystemExit(f'{name}: missing modules.txt')
print('All registered application packages are importable.')
CHECK_APPS
phase "Preparing site database"
if [[ ! -f "sites/$site/site_config.json" ]]; then
  if [[ -d "sites/$site" ]]; then
    echo "Site directory exists without site_config.json. Refusing to overwrite it; inspect the interrupted site setup." >&2
    exit 1
  fi
  bench new-site "$site" --db-type mariadb --db-host db --db-root-password "$DB_ROOT_PASSWORD" --admin-password "$ADMIN_PASSWORD" --mariadb-user-host-login-scope='%'
fi
bench --site "$site" execute frappe.get_installed_apps
phase "Installing site apps and migrating"
for app in payments lms nightjar_learning; do bench --site "$site" install-app "$app"; done
bench --site "$site" set-config developer_mode 1
bench --site "$site" migrate
phase "Checking release APIs, database and Redis writes"
bench --site "$site" execute nightjar_learning.deployment.check
asset_revision="$(env/bin/python -c 'import hashlib,pathlib; print(hashlib.sha256(b"".join(p.read_bytes() for p in sorted(pathlib.Path("/workspace/deploy/patches").glob("*.patch")))).hexdigest())')"
if [[ ! -f .nightjar-native-assets ]] || [[ "$(< .nightjar-native-assets)" != "$asset_revision" ]]; then
  phase "Building Frappe and LMS assets"
  bench build --app frappe
  yarn --cwd apps/lms/frontend install --frozen-lockfile
  yarn --cwd apps/lms/frontend build
  printf '%s\n' "$asset_revision" > .nightjar-native-assets
fi
phase "Building Nightjar assets"
npm --prefix apps/nightjar_learning/frontend ci
npm --prefix apps/nightjar_learning/frontend run build
bench --site "$site" clear-cache
bench use "$site"
phase "Starting development services"
exec bench start
