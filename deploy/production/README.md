# Nightjar production deployment

This bundle runs Nightjar as an isolated Frappe production stack. It does not
reuse the development Compose file in `deploy/compose.yaml`.

Properties:

- Exact Frappe, LMS and Payments revisions from `docs/IMPLEMENTATION.md`.
- Official Frappe v15.122.0 build/runtime images pinned by amd64 digest.
- Separate MariaDB, Redis, sites, logs and media storage.
- Only the frontend is published, on `127.0.0.1:8088` by default.
- Developer mode is disabled; Gunicorn, workers and scheduler are separate.
- Private media acceleration is initially disabled. Gunicorn performs the
  authorization checks and serves protected media.

Never run `docker compose down -v`: `-v` deletes the Nightjar database and site
volumes. Back up the site and export its backup outside Docker before upgrades.

## Automatic GitHub deployment

The repository workflow builds an immutable image for the exact pushed commit,
publishes it to GitHub Container Registry, then connects with a dedicated SSH
account. The server deployer serializes releases, verifies the commit and image
label, creates a Frappe backup, exports it under
`/opt/nightjar-learning/deployment-backups`, updates only the
`nightjar-learning` Compose project, and performs a local health check. It does
not run `docker compose down` and never removes volumes. If startup fails it
attempts to restore the previous image.

One-time setup is documented in `docs/GITHUB-DEPLOYMENT.md`.

