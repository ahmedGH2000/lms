# Implementation plan and architecture

## Phase 1 — Inspect and reuse

The official `frappe/lms` repository was cloned and inspected before extension work. Inspected Vue routing, lesson rendering, Python API/permission hooks, enrollment/payment/progress controllers, discussion behavior, DocType JSON schemas, and the installed MariaDB schema. Frappe is a Python/MariaDB backend with Redis sessions and jobs. LMS uses Vue/Frappe UI and stores courses → chapter references → chapters → lesson references → lessons. Native authoring and assessments remain available.

Pinned stable baseline (version-15 branches):

| App | Version/revision |
|---|---|
| Frappe | 15.122.0 — `b0b5b99a1d9d2cb3d54b32293d3854bf2c15f4a4` |
| Learning | 2.63.0 — `87168fc7b2f24559e474ea4702cf1aa63b0db4e8` |
| Payments | `9885a6e500104f1f160add47d55b370773e67a81` |

Develop required a newer Python/Frappe stack. Stable v15 was selected for this build. These pins record the tested baseline, not a promise of indefinite security support; review advisories and run regression tests before upgrades.

## Phase 2 — Learning experience

Dembrandt/Manavarya09 extraction files supplied by the user informed the design: midnight navy surfaces, electric blue highlights, Hanken Grotesk, generous headings, a 4-pixel spacing rhythm, rounded panels and a 3-column catalog. Invalid crawler color/body-size values were discarded. Nightjar has original branding, geometric CSS course illustrations, copy, layouts and code-window hero. No Laracasts logo, course artwork, proprietary font, or course content is included.

The custom Vue app is served by Frappe at `/learn`; it uses same-origin cookie sessions and Frappe CSRF tokens. Typography is self-hosted. Shaka is loaded only for private video lessons. Layout adapts to desktop, tablet and phone with keyboard focus, skip navigation, modal focus handling and reduced-motion support. Chromium responsive and account-form checks were added on October 14; see TEST-RESULTS.md for the tested boundaries.

## Phase 3 — Authorization and manual payments

Use native users/roles, LMS Course, Course Chapter, Course Lesson, LMS Enrollment, LMS Course Progress, Discussion Topic and Discussion Reply. Add four small DocTypes: NJ Payment Request, NJ Video Asset, NJ Video Position and NJ Playback Event. Add namespaced custom fields for difficulty, explicit administrator enrollment approval and reply threading.

Students submit a transfer reference; prices/currency come from the course on the server. System Managers record a verification note and approve/reject. Approval and native enrollment happen in one database transaction; course locks serialize duplicate enrollment/request operations. Revocation removes enrollment. No browser-submitted paid flag is trusted. Administrators may also explicitly grant enrollment.

Permission hooks cover document reads, list queries, enrollment/payment/progress writes, native lesson retrieval, lesson resources and discussion. Only assigned instructors may access another learner's course content; a global Course Creator role alone does not grant paid playback. Private learner records remain member-scoped except for System Managers. Existing unpaid imported enrollments need explicit review before paid access.

## Phase 4 — Media

A local CLI packages trusted source video into one 720p-or-smaller AES-128 HLS rendition. Store its UUID directory outside public Frappe files and attach its metadata to a lesson. The browser obtains a 300-second HMAC grant tied to account, session, asset and lesson. Every manifest/key/segment request rechecks authorization. NGINX may serve already-authorized segments with an internal redirect; the backend serves keys and manifests. Shaka renews authorization, displays a moving account identifier, and sends bounded resume telemetry.

## Phase 5 — Verification and handoff

Build all frontends; exercise real Frappe requests, payment transitions, cross-account denial, media grants/keys/segments, token replay/expiry, filesystem escapes and FFmpeg decode. Deliver tests and clearly mark browser/Compose/email checks that could not run here.

## Upgrade boundary and backlog

Most changes live in the separate app, using a small set of class and whitelisted-method overrides. Three reviewed patches now also apply to the exact pinned upstream revisions: Frappe avoids a redundant global-default write during User validation; LMS's two member forms use the atomic Nightjar endpoint and show persistent feedback. `deploy/apply_upstream_patches.py` checks exact revisions, validates every patch before applying any, skips already-applied patches and refuses conflicting edits without resetting source. Patch changes invalidate the native-asset build marker. Before upgrading either upstream app, port/review these patches and rerun regressions; do not disable the revision check. Removing Nightjar also requires reversing its LMS form patch and rebuilding assets so the forms stop calling the custom endpoint. The third patch adds a content-only native activity renderer inside the Nightjar lesson, preserving upstream quiz and EditorJS behavior. A real quiz submission is covered by the current browser regression; other advanced block variants and certificate/batch flows are not comprehensively tested. See UPDATE-2026-10-15.md.

Next release gates: browser QA and accessibility audit; complete upstream permission review (including batches, private notes and reports); gateway signature/replay handling; caption authoring and adaptive renditions; stronger operational monitoring, backup/restore and load tests. Search currently targets course titles, not lesson full text. Discussion and dashboard APIs have bounded result sizes; add pagination for large cohorts.
