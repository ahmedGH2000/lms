# Arabic and English preview

This working tree contains the unreleased `2026.10.26-preview.1` bilingual preview. It has not been pushed, published, or deployed.

## Included

- Arabic is the default language. A visible Arabic/English control applies to `/learn`, `/lms`, and `/app`, remembers the browser preference, and saves it to signed-in accounts.
- `/learn` has a complete RTL layout and translated interface. Course, chapter, and lesson content can be stored independently in Arabic and English.
- Content fallback is deterministic: selected language, then the other translation, then the original LMS value.
- Assigned instructors can edit translations only for their own courses. System managers can edit all courses from `/learn#view=translations`.
- The catalog has a solid, multi-face CSS 3D pyramid, scroll-linked decorative motion, and card reveals. Motion is absent from lesson, video, and quiz views and disabled when reduced motion is requested.
- The original LMS fields remain the source fallback, so existing courses are not destructively migrated.

## Verification completed

- Production Vue build.
- Python regression suite: 116 passing tests.
- Headless Chromium regression flow with mocked APIs: 15 passing checks, including RTL persistence and reduced-motion behavior.
- Release manifest verification and static syntax checks.
- Production dependency audit: no known vulnerabilities.

## Before publishing

Run the preview against a disposable Frappe site, execute migrations so the translation custom fields are created, and verify Arabic and English content editing with real instructor and student accounts. Also check upstream `/lms` and `/app` pages against the pinned Frappe/LMS revisions; their core Arabic strings come from upstream translation catalogs.

Do not push to `main` until that live-site pass is complete, because this repository's production workflow deploys `main` automatically.
