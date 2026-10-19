# Nightjar Learning

**Existing installations:** use [the complete-update repair instructions](docs/REPAIR-2026-10-15.md) for release 2026.10.15.2. This replaces manual source merging.

An original dark learning experience on **Frappe Learning**, with enrollment-backed AES-HLS video access. AGPL-3.0-or-later. The official LMS remains the source of truth for courses, teaching, accounts, enrollment, assessment requirements, and completion.

Open `/learn` for the student website and everyday administration; `/lms` for staff course authoring; `/app` for advanced administrator settings. Nothing is published automatically.

- Responsive catalog, search, category and difficulty filters, original course illustrations, course outlines, and student dashboard.
- Custom signup with chosen passwords, login, recovery, profile/password settings and student management, backed by native Frappe authentication and roles.
- Manual payment request, administrator approval/rejection/revocation, and a server-only extension point for future verified gateway payments.
- Private AES-128 HLS, 5-minute session-bound grants, enrollment checks on every media request, Shaka controls, account watermark and resume position.
- Lesson discussions with student/instructor replies and administrator moderation; course reviews with instructor responses.
- Native rich-content and quiz components embedded inside the custom lesson page.

Start with [docs/SETUP.md](docs/SETUP.md). See [implementation and design decisions](docs/IMPLEMENTATION.md), [security model](docs/SECURITY.md), and [verification results](docs/TEST-RESULTS.md).

## What is included

A separate installable Frappe app, Vue source and prebuilt UI, pinned upstream revisions, three reviewed upstream patches, local Compose recipe, FFmpeg packager, optional NGINX media snippet, regression tests, and six optional starter courses. Starter courses contain short practice prompts, not complete video curricula. Supply your own course videos and payment instructions.

Updating an existing installation? Follow [UPDATE-2026-10-15.md](docs/UPDATE-2026-10-15.md). This update unifies the student journey and adds registration passwords, reviews, moderation and everyday account management. Keep your existing environment file and database volumes.

## Honest delivery boundary

The custom UI and upstream applications were built; backend flows were exercised against MariaDB, Redis, and real Frappe sessions. Chromium browser tests now cover account forms and responsive layouts. Docker startup, real email delivery, physical-phone/Safari behavior, and complete video-player compatibility still require validation. See the test report for precise coverage. This is a development implementation, not a production security certification.
# lms
