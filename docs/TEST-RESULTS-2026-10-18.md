# Release 2026.10.18.1 — validation

These results describe this update. Historical test reports in this project describe earlier releases and must not be treated as live integration coverage for the new receipt/reviewer code.

## Completed checks

- **102 Python tests passed.** This includes the existing 43 regression tests plus receipt parsing/normalization, JPG/PNG/PDF restrictions, size checks, PDF active-content rejection, instructor/admin/student permission matrices, reviewer course filtering, private download authorization, request transitions, enrollment approval context, rejection of client-supplied permission flags, student routing, native activity exceptions, receipt cleanup and response headers, and process-scoped local backup behavior.
- **14 Chromium checks passed against the built student UI with API doubles.** Newest-course thumbnail, missing-image fallback, layouts at 320/390/768/1440px, reduced-motion behavior, signup redirect/confirmation, cleared password, staff/student landing pages, phone receipt dialog, unsupported file rejection, required text, retaining form contents after failure, multipart text+receipt/CSRF, and text-only requests. No uncaught browser errors.
- **Native LMS payment component built and exercised in Chromium with API doubles.** Receipt links, required review notes, approve/reject/revoke, cancelling revoke confirmation, status filters, error state clearing, and layouts at 320/390/768/1280px. No uncaught browser errors. Visual inspection corrected the review-label layout and mobile dialog stacking.
- **Production student UI build passed.** The prebuilt assets are included. The existing Shaka player chunk still exceeds Vite's size advisory threshold.
- **Full pinned LMS production build passed** with all three Nightjar LMS patches in a temporary Bench-shaped source tree. Only a synthetic local port configuration was supplied; no database was running. Dependency versions and integrity hashes remained those of the upstream lockfile (package downloads used the npm registry mirror). Existing upstream bundle-size and PWA precache warnings remain.
- **Upstream patch compatibility passed** on LMS commit `87168fc7b2f24559e474ea4702cf1aa63b0db4e8`: new payment patch plus existing lesson-activity and member/feedback patches apply together and reverse-check cleanly. The original Frappe patch is unchanged. Bootstrap still refuses a different upstream revision or conflicting source changes.
- Python compile checks and Bash syntax checks passed. The final release manifest verifies the bundled app files and enumerates both student and LMS payment APIs.

## What was simulated

Frappe boundary tests use in-memory doubles. They execute the actual Nightjar permission and workflow functions, but do not simulate transaction isolation, MariaDB locks, or every Frappe lifecycle hook. The existing updater tests execute real shell/Python file copying with simulated Docker calls, proving backup/preflight failures stop copying and `.env`/Compose/user files are retained. Backup-client tests use fake executables and confirm only the Compose host `db` receives the TLS compatibility argument; external hosts keep their TLS settings.

Browser APIs use deterministic test data, not a live Frappe session. Receipt server tests separately validate actual image/PDF bytes. Screenshots used invented test courses/accounts and were used only for inspection.

## Still needs the installed site

Run the updater and let migration/assets finish, then check one real student receipt request, course-instructor approval, rejection/revocation, another instructor's denied access, and an embedded lesson activity. This environment has no Docker/MariaDB/Redis installation and has not executed your running site's migration, full backup/restore, email delivery, or real-session end-to-end approval transaction. No existing student data was accessed or changed here.

## Reproduce local checks

From the project root, with pytest, Pillow, pypdf, Werkzeug, FFmpeg/ffprobe, Git and Bash available:

```bash
python3 -m pytest tests -q
```

Build the student UI with `npm ci` and `npm run build` from `frontend`. With Playwright/Chromium available, run `node scripts/browser_update_check.cjs` from the project root. `CHROMIUM_PATH` and `PLAYWRIGHT_MODULE` can select an installed browser/package. These browser checks never connect to a real site.

The native LMS component check used the exact Vue component from the new patch in a temporary Vue harness, replacing only the Frappe UI network function. The full LMS source check used the pinned source with all three Nightjar LMS patches.
