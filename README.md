# Nightjar Learning

**Release 2026.10.18.1 — existing installations:** use [the update instructions](docs/UPDATE-2026-10-18.md). Run the updater from the new download; it backs up and updates your existing project.

An original dark learning experience on **Frappe Learning**, with enrollment-backed AES-HLS video access. AGPL-3.0-or-later. The official LMS remains the source of truth for courses, teaching, accounts, enrollment, assessment requirements, and completion.

Students use `/learn`. Instructors and administrators land on `/lms`, with payment reviews at `/lms/payment-requests`; staff can also visit `/learn`. `/app` remains available for advanced administrator settings. Nothing is published automatically.

- Responsive catalog, search, category and difficulty filters, original course illustrations, course outlines, and student dashboard.
- Custom signup with chosen passwords, login, recovery, profile/password settings and student management, backed by native Frappe authentication and roles.
- Payment requests with required text and optional private JPG/PNG/PDF receipts. Assigned instructors approve/reject/revoke their courses; administrators manage all courses.
- Private AES-128 HLS, 5-minute session-bound grants, enrollment checks on every media request, Shaka controls, account watermark and resume position.
- Lesson discussions with student/instructor replies and administrator moderation; course reviews with instructor responses.
- Native rich-content and quiz components embedded inside the custom lesson page.

Start with [docs/SETUP.md](docs/SETUP.md). See [implementation and design decisions](docs/IMPLEMENTATION.md), [security model](docs/SECURITY.md), and [verification results](docs/TEST-RESULTS.md).

## What is included

A separate installable Frappe app, Vue source and prebuilt UI, pinned upstream revisions, four reviewed upstream patches, local Compose recipe, FFmpeg packager, optional NGINX media snippet, regression tests, and six optional starter courses. Starter courses contain short practice prompts, not complete video curricula. Supply your own course videos and payment instructions.

This update adds course thumbnails in the featured area, subtle motion, improved alerts, signup-to-sign-in redirects, role-based login destinations, receipts, and native LMS payment review. Keep your existing environment file and database volumes.

## Validation boundary

See [this release’s checks](docs/TEST-RESULTS-2026-10-18.md). This release was checked with Python regression tests, production UI builds, and Chromium tests using API doubles. The existing project includes historical live-site test reports, but they do not certify these new changes. The new migration, complete Docker update, and real-database approval/upload flows must still be checked on the installed site. The updater preserves the database and takes a backup before copying files.
