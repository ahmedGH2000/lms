For an existing installation, use [the release repair updater](REPAIR-2026-10-15.md). Keep the existing database and environment.

> Current student/account workflow and existing-installation update: [UPDATE-2026-10-15.md](UPDATE-2026-10-15.md). Students start at `/learn`; registration now accepts their chosen password.

# Local installation and development

## Requirements

Linux/macOS with a Frappe-compatible toolchain, or Docker Engine plus Compose. The local regression runtime used Python 3.12, Node 24, Yarn 1.22, MariaDB 10.11 and Redis. This pinned LMS frontend requires Node 22 or newer. Use a toolchain compatible with the pinned Frappe revision; the changing Docker image's Python 3.14 environment has not been certified here. FFmpeg/ffprobe are needed to package source videos. Allow several GB for dependencies and database storage.

The tested revision pins are in IMPLEMENTATION.md. Do not mix this app with Frappe develop/v17. Native installation was tested here with isolated MariaDB/Redis and real Frappe sessions. The Docker recipe is supplied but was not executed because this environment has no Docker daemon.

## Option A: supplied local Compose recipe

From the extracted project root:

```bash
mkdir -p private-media
cp deploy/.env.example deploy/.env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Generate three independent values and place them in `deploy/.env` as `DB_ROOT_PASSWORD`, `ADMIN_PASSWORD` and `NIGHTJAR_VIDEO_SECRET`. Set `MEDIA_PATH` to the absolute path of `private-media`. Protect the file with `chmod 600 deploy/.env`. It is ignored by Git. Do not use a real account password for these development credentials.

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml up
```

First startup clones official repositories at the recorded commits, installs dependencies/apps, migrates, and builds assets. It can take several minutes. The recipe only binds localhost ports. Open `http://nightjar.localhost:8000/learn`; if your OS does not resolve `.localhost`, add `127.0.0.1 nightjar.localhost` to your hosts file. Sign in at `/login` as `Administrator` with the password you generated. `/lms` opens native learning/authoring; `/app` opens Desk.

The Docker development image tag is configurable with `BENCH_IMAGE`. Resolve and pin an image digest in your own environment for repeatable infrastructure. App commits and custom frontend dependencies are pinned. Database and bench state use named volumes. `docker compose ... down` stops the stack and preserves them; do not use `down -v` unless you intend to delete the development database.

The project is copied into the bench on container startup. After changing source, restart the app container to copy/build it again. For faster local iteration, use the native bench below.

### Recovering from the earlier bootstrap failures

For the current update, follow [UPDATE-2026-10-14.md](UPDATE-2026-10-14.md).
Replacing only `deploy/init.sh` is no longer sufficient: it now uses the bundled
patch helper and patch files, and account fixes also require updated app/frontend
source. Keep `deploy/.env`, private media and Docker volumes. No database reset
is needed for these account fixes.

The revised script repairs the exact `lmsnightjar_learning` (or corresponding
Frappe/Payments) concatenation left by the old script, preserves the original list
as `sites/apps.txt.before-nightjar-repair`, and writes separate newline-terminated
app names. It checks all registered app imports before attempting site creation.
Named stages identify whether a subsequent failure is in dependencies, imports,
the database, assets, or service startup. A partially created site directory is
never deleted or forcibly reinstalled. Existing site configuration leads to a
database check before migrations; a database error requires diagnosis, not a reset.

The Redis overcommit and MariaDB io_uring warnings in the reported logs did not
cause these application exits: both services reached their ready states. They
should not be confused with the final application traceback.

This remains a development bootstrap, not a verified prebuilt Docker distribution.
`frappe/bench:latest` can change its Python, Node and Bench versions over time.
The script checks Node >=22, but this does not certify every future toolchain
combination. Before wider distribution, build and test an image with fixed base
image digest, Python/Node/Bench versions, upstream commits, and installed assets;
exercise both empty-volume startup and restart/recovery in CI. Do not publish that
image or expose this development stack without an explicit deployment decision.

## Option B: existing stable v15 bench

Keep normal Frappe services running. Back up an existing site before installation. From your bench directory, install/checkout the official apps if not already installed:

```bash
bench get-app --branch version-15 https://github.com/frappe/payments
bench get-app --branch version-15 https://github.com/frappe/lms
git -C apps/frappe checkout b0b5b99a1d9d2cb3d54b32293d3854bf2c15f4a4
git -C apps/payments checkout 9885a6e500104f1f160add47d55b370773e67a81
git -C apps/lms checkout 87168fc7b2f24559e474ea4702cf1aa63b0db4e8
bench setup requirements
```

Copy the extracted **contents** of this project into `apps/nightjar_learning`. Use a real directory for LMS under `bench/apps/lms`: its frontend imports `sites/common_site_config.json` relative to that path. Ensure the usual `socketio_port` entry exists (normally 9000).

```bash
./env/bin/pip install -e apps/nightjar_learning
./env/bin/python apps/nightjar_learning/deploy/apply_upstream_patches.py "$PWD"
# Add nightjar_learning to sites/apps.txt once, on its own line.
bench --site nightjar.localhost install-app payments
bench --site nightjar.localhost install-app lms
bench --site nightjar.localhost install-app nightjar_learning
bench --site nightjar.localhost migrate
bench build --app frappe
yarn --cwd apps/lms/frontend install --frozen-lockfile
NODE_OPTIONS=--max-old-space-size=6144 yarn --cwd apps/lms/frontend build
npm --prefix apps/nightjar_learning/frontend ci
npm --prefix apps/nightjar_learning/frontend run build
bench --site nightjar.localhost clear-cache
bench use nightjar.localhost
```

For a fresh bench, first use the official [Frappe installation instructions](https://docs.frappe.io/framework/user/en/installation), `bench init --frappe-branch version-15`, then `bench new-site nightjar.localhost`. Set MariaDB/Redis appropriately before `new-site`. Do not overwrite an existing site's configuration with a sample file.

Set `NIGHTJAR_VIDEO_SECRET` (at least 32 random bytes represented as text) and `NIGHTJAR_MEDIA_ROOT` in the environment of **all web workers** before starting them. Then `bench start` for local development. Restart workers after changing secrets or configuration. `NIGHTJAR_USE_ACCEL` defaults off, so the backend serves segments without NGINX locally.

For UI iteration:

```bash
cd apps/nightjar_learning/frontend
npm run build -- --watch
```

Keep `bench start` running separately and refresh `/learn`. This uses the real same-origin authenticated backend, avoiding a separate mock API or cross-origin session configuration.

## Accounts, authoring and payment approval

Sign in as `Administrator` using the password originally supplied by `ADMIN_PASSWORD` when the site was created. Changing that environment variable later does not reset an existing account.

In native LMS Settings, open Signup Settings and turn **Disable Signup** off, then save. Confirm Website Settings also has Disable Signup unchecked. Native LMS synchronizes this setting when it changes. In a logged-out/private browser window, open `/login#signup` to verify that the form is available. Configure an outgoing Email Account and test delivery before inviting learners; signup without outgoing email creates an account but cannot deliver the password setup link. The new feedback explicitly reports that condition. Never give learners the administrator password. Learners manage their native profile at `/me`.

To add an instructor, sign in as Administrator and open `/lms/settings/users/new` (or Settings → Users → Add). Enter their email and first name, enable **Course Creator**, and Save. The new endpoint creates the account and selected learning roles atomically. It requires both native User-create permission and Moderator permission (Administrator is allowed). A Course Creator alone cannot manage other users. Duplicate emails must be edited as existing users, not re-created. No System Manager role can be assigned through this endpoint. A visible confirmation explains whether a password setup email was queued; actual delivery still depends on mail configuration.

Give teachers the native `Course Creator` role and assign them to their courses' instructor tables. Use `/lms` to create courses, chapters, lessons, categories and rich activities. Set `Difficulty` on LMS Course in Desk. Course visibility and self-enrollment remain controlled by native fields. The custom experience enforces native sequential lesson requirements.

For a paid course, set its price/currency and provide your transfer instructions in its public description. A learner submits a reference in Nightjar. A System Manager opens **Payment review**, verifies receipt outside the application, and records a note before approval. A submitted reference is never proof of payment. Rejection keeps access closed; revocation removes enrollment. Direct administrator enrollment is also an explicit approval. Review legacy paid enrollments before migration.

Optional starter courses, only on a development site:

```bash
bench --site nightjar.localhost set-config developer_mode 1
bench --site nightjar.localhost execute nightjar_learning.demo.seed
```

This creates six sample courses with practice prompts, no demo accounts and no real videos. Do not seed a production site.

## Private video ingestion

```bash
python3 apps/nightjar_learning/scripts/package_video.py /absolute/path/lesson.mp4 \
  --root /absolute/path/private-media
```

The command outputs an `asset_id` and duration. In Desk create **NJ Video Asset**, choose the Course Lesson, paste those two values, and enable Active. The associated lesson in `/learn` now loads Shaka. Retain the original source offline for re-encoding; do not attach its public URL to lesson content. The private directory must be readable by Frappe; for NGINX acceleration it must also be readable by the NGINX worker. Use ownership/shared-group permissions, never world-readable public storage. For Docker, align host file ownership with the container's user.

The packager creates a single AES key per asset and 6-second segments. Captions/multiple renditions are future ingestion work. Neither private media nor signing secrets belong in Git, site public files or the source archive.

For optional accelerated streaming, adapt `deploy/nginx-media.conf` into the existing Frappe NGINX server, adjust its upstream and absolute media root, validate with `nginx -t`, then set `NIGHTJAR_USE_ACCEL=1` on Frappe web workers. Use HTTPS outside loopback development. The snippet is an integration fragment, not a complete production TLS configuration.

## Tests

```bash
./env/bin/pip install pytest
./env/bin/python -m pytest apps/nightjar_learning/tests -q
```

The optional integration script uses real Frappe WSGI sessions and your database. **Use a disposable `.localhost` site with developer mode enabled.** It seeds sample courses, creates example.invalid regression users, resets only their test enrollments/progress, and changes their passwords. It deliberately tests malicious requests. It is not a production smoke test.

Prepare a short video with FFmpeg, package it to your private media root, save the JSON output to a file, and export:

```bash
export FRAPPE_BENCH_ROOT="$PWD"
export NJ_TEST_SITE=nightjar.localhost
export NJ_RUN_INTEGRATION=1
export NJ_TEST_MEDIA_METADATA=/absolute/path/video-metadata.json
export NIGHTJAR_MEDIA_ROOT=/absolute/path/private-media
# Set NJ_TEST_ADMIN_PASSWORD privately to this disposable site's administrator password.
./env/bin/python apps/nightjar_learning/scripts/integration_check.py
```

The script writes `integration-results.json` to the current directory. Optional Linux NGINX smoke testing is enabled with `NJ_NGINX_BIN=/absolute/path/nginx`; it needs localhost ports 18000/18880 available and access to the media tree. Its root-worker configuration is limited to this local smoke test, not deployment.
