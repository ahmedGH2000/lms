# Verification report — updated 2026-10-15

## Release 2026.10.15.2 — incomplete-update repair

| Current check | Result |
| --- | --- |
| Custom frontend API contract/imports | All 27 called methods import from the expected installation and are whitelisted |
| Backend account/community/permission checks | 35 passed |
| Payment, enrollment, private-video and authorization regression | 45 passed |
| Unified Chromium interaction/responsiveness suite | 23 passed |
| Catalog and deployment-error Chromium scenarios | 9 passed |
| Unit, bootstrap, partial-release and updater tests | 43 passed |
| Custom Vue production build and Python/shell syntax | Passed |
| Installed-release readiness check | Database, temporary Redis write/read and review schema passed |
| Actual Docker updater on a host | Not run: Docker unavailable in this environment |

The supplied log establishes that the running backend lacks the new login/signup
methods and community module while the browser calls them. The previous delivered
archive contains them. We cannot identify the user's exact mounted/imported
folder from that log alone; the new updater and runtime import checks detect the
mismatch directly. Source completeness, Python import location and API whitelisting
are now checked before serving. A release manifest is an integrity/completeness
check, not an authenticity signature.

Focused browser cases exercise all difficulty values/reset using the real backend;
HTTP 500 after a filter change and on initial load; retry; out-of-order failed
responses; legitimate empty search/clear filters; a missing signup endpoint; and
an incompatible server boot payload. Failure responses/old boot are deliberately
intercepted to test the UI. Normal learning/account actions use real Frappe and
MariaDB. No uncaught browser errors occurred in the completed suites.

The updater tests run actual shell/Python copying with simulated Docker commands.
They verify existing .env/Compose/unrelated files remain intact, old source is
backed up, site backups are exported, the app is recreated, and backup/startup
configuration failures stop before copying. Separate tests reject missing/edited
source, missing API methods, unregistered methods and Python imports from an old
installation. These are not substitutes for testing on the user's Docker host.

During verification, a query-string cache-busting approach reloaded the entry
module when the lazy player imported it. It was replaced with Vite's content-hashed
entry and manifest; the full lesson/player-loading browser flow then passed.
QA startup-wait and hostname-resolution assumptions were also corrected in the
new test harness; those were test-environment issues, not application fixes.

Use `scripts/recovery_browser.cjs` with `NJ_RUN_INTEGRATION=1`, a disposable
`.localhost` `NJ_BASE_URL`, and optional `PLAYWRIGHT_MODULE` / `CHROMIUM_PATH`.
It expects published starter courses including a Beginner course. It writes
`recovery-browser-results.json` locally. Evidence is included beside this report.
The earlier video-playback browser evidence remains historical; current video
backend authorization checks were rerun. SMTP, real phones, load testing and
advanced activity variants remain outside this pass.

## Prior unified-experience evidence

### October 15 unified experience

The current update passed **35 backend checks**, **23 Chromium browser checks**,
**45 existing payment/access/video integration checks**, and **34 unit/bootstrap/patch checks**.
The custom Vue and native LMS production builds passed. These ran on native
MariaDB/Redis/Frappe in the test environment; Docker itself was unavailable.

New coverage includes password-at-signup and role-injection rejection, custom
login/logout, own-profile changes, current-password validation, administrator
student creation/password setting, cross-student permission denial, enrolled
reviews, instructor responses, peer discussion replies, administrator moderation,
CSRF, student route redirection, and an actual native quiz answer submission
inside the custom lesson. Browser widths were 320, 390, 768, 1024 and 1440 pixels.
The browser recorded no uncaught page errors. See `unified-test-results.json`
and `unified-browser-results.json`. Expected permission-denial tests produce
server exception traces; every assertion passed.

Fixed during this iteration: stale Guest boot state after custom login,
null profile fields, profile loading races, and session/CSRF refresh after a
password change. Native quiz read/answer/submit endpoints now recheck custom
course entitlement and lesson gates.

The video playback browser evidence below is from October 14; video authorization,
key/segment access and revocation tests were rerun October 15. SMTP delivery,
real-device browsers and advanced activity variants remain unverified. Read
`UPDATE-2026-10-15.md` for safe update instructions and remaining limitations.

## Earlier verification and regression context

Tests ran against the pinned Frappe 15.122.0 / LMS 2.63.0 revisions, the installed custom app, MariaDB 10.11 and Redis. Tests used actual Frappe WSGI middleware, CSRF/session cookies and database transactions, not a mocked API. Native services ran locally and were stopped after test runs.

| Check | Result |
|---|---|
| Custom Vue production build | Passed; Shaka is a separate lazy-loaded chunk |
| Native Frappe assets | Passed |
| Native LMS assets | Passed; needed a normal bench directory layout and a 6 GB Node heap limit in this environment |
| Real Frappe integration suite | 45 passed, 0 failed; rerun October 15; earlier separate NGINX smoke test also passed |
| Token, filesystem, FFmpeg, bootstrap and patch-safety tests | 34 passed, 0 failed |
| Real-database account/lock regressions | 20 passed, 0 failed |
| Custom frontend production dependency audit | 0 reported advisories at delivery |
| Python compile and bootstrap shell syntax | Passed |
| Chromium browser interactions and responsive layouts | 35 passed, 0 failed; headless Chromium 153 / Playwright |
| Real Shaka browser playback | Synthetic encrypted HLS played; watermark and pause heartbeat verified in Chromium |
| Extended video/browser compatibility | Renewal beyond five minutes, fullscreen/PiP, real-device Safari/Firefox not verified |
| Docker Compose startup | Not run; no Docker daemon available |
| Outbound email and live payment gateway | Not run; no external mail/gateway credentials configured |

## Integration coverage

Guest catalog; native registration; incorrect password rejection; student/admin/instructor login and page boot; free enrollment; paid enrollment denial before approval; manual request; student approval denial; pending-content denial; admin approval and retry; paid access; cross-student denial; assigned versus unrelated instructor access; comments and instructor replies; private discussion denial; real completion percentage/dashboard; private video grant; unauthorized grant denial; AES manifest, key and encrypted segment delivery; no-store headers; cross-session token replay denial; traversal denial; playback position save and bounds; payment revocation; generic REST enrollment/data/payment forgery denial; missing CSRF rejection; generic discussion/lesson list filtering; native lesson endpoint denial; guest token denial; existing token invalidation after enrollment deletion.

The NGINX test started a local NGINX process and a real Frappe WSGI HTTP server. It verified direct internal-path 404, authenticated X-Accel segment delivery byte-for-byte, no-store headers, and denial without the Frappe session. It exercised the supplied NGINX location snippet after substituting the local test media path/upstream.

The FFmpeg test generated a short synthetic source, encrypted it with the supplied packager, verified key permissions, and decoded the resulting HLS with its key. The October 14 browser run also loaded and played that encrypted stream in Chromium. This is not comprehensive codec or cross-browser compatibility testing.

## October 14 account and browser regression

The original Frappe `ask_pass_update()` was executed with its shared DefaultValue
row deliberately locked by a second MariaDB connection: it timed out. The patched
function returned without waiting, and real native signup and instructor creation
succeeded while the lock was held. Remaining cases check duplicate/malformed
accounts, missing names, malformed role payloads, missing CSRF, guest/student permission denials, forbidden privileged
roles, actual saved Course Creator/student roles, and rollback of the entire User
insert when evaluator creation fails. These tests do not identify the original
blocking transaction on the user's machine. See account-test-results.json.

The browser run used actual local Frappe sessions and database writes. It covers
signup with missing-email guidance; admin/student login; mobile instructor save;
double-click protection; persistent duplicate/server/network errors; catalog
error recovery; free enrollment; paid request without access; comments and
completion; dashboard enrollment; mobile dialog scrolling/Escape; student denial
on member management; encrypted video playback/watermark/heartbeat; catalog
widths 320, 390, 768, 1024 and 1440; lesson widths 320, 390, 768 and 1440. No
uncaught page JavaScript errors occurred in the completed run. Server and network
failure cases were deliberately intercepted; happy paths used the real backend.
Screenshots were reviewed internally for the catalog, signup and member forms.
See browser-test-results.json. Physical-phone testing and a full accessibility
audit remain outstanding.

Issues fixed during this pass: redundant global default writes during User
validation; non-atomic member/role creation; missing persistent errors; an error
formatter assuming a message always exists; generic server-error wording; low
contrast in the native theme's error token; signup duplicate-submit/connection
feedback; responsive wrapping/navigation/dialog behavior; and Shaka's unnecessary
HEAD probe (the HLS MIME type is now passed explicitly). Starter-course seeding
also recomputes derived lesson counts after linking chapters and on repeat runs,
without replacing lesson content.

Patch-safety regressions use real temporary Git repositories and check apply,
repeat apply, unknown revisions, conflicting edits, and all-patches validation
before mutation. Bootstrap lifecycle tests use simulated external build/services
and verify changed patches trigger an asset rebuild without a second site
creation. These are not Docker end-to-end tests.

### Re-running focused tests

Run `python -m pytest tests -q` from the project root with the app importable,
pytest installed, and Git, Bash, FFmpeg/ffprobe on PATH.
For account checks, use a **disposable** `.localhost` development site with all apps
installed and these patches applied, set `NJ_RUN_INTEGRATION=1`,
`FRAPPE_BENCH_ROOT`, `NJ_TEST_SITE`, and `NJ_TEST_ADMIN_PASSWORD`, then run
`./env/bin/python apps/nightjar_learning/scripts/account_check.py` from the bench.
It inserts test users and changes signup/default settings; never run it on a
valuable database.

`scripts/browser_check.cjs` is the reusable browser harness. Install Playwright
and Chromium in a separate QA environment, expose it via `PLAYWRIGHT_MODULE` if
not normally resolvable, and set `NJ_RUN_INTEGRATION=1`, `NJ_BASE_URL`,
`NJ_TEST_ADMIN_PASSWORD`, and `NJ_BROWSER_FIXTURE`. Optional `CHROMIUM_PATH`
selects an already-installed browser. The fixture is a private JSON file with
`email`, `password`, `free`, `paid` and `lesson`: a fresh student account, the two
course document names, and the first free lesson name. Seed the supplied starter
courses and attach a packaged playable video to that first lesson. The student
must start without enrollment/payment requests; configure signup enabled and
outgoing mail disabled for the specific no-email assertion. The suite creates
accounts, comments, enrollment, completion and payment-request records. Use only
disposable test data. It does not reset real users or deploy anything.

## Problems found and fixed

- Restored native app directory layout and socketio configuration required by LMS's relative build imports.
- Used a larger Node heap for the upstream LMS build after a default-heap exhaustion.
- Corrected the seed script's stale document timestamp after chapter creation.
- Added server gates to native lesson/file and generic document/list paths, alongside custom APIs.
- Suppressed native global discussion broadcasts for protected lesson discussions.
- Corrected a hash-router skip-link collision and guarded the asynchronous player's unmount lifecycle.
- Fixed quoting of NGINX regex quantifiers; the live proxy smoke test now passes.
- Updated custom Vue/DOMPurify dependencies after the initial audit and rebuilt.

Some initial test assertions expected a different rejection status or a message body on a successful void DELETE. Those assertions were corrected to Frappe's actual response contract; authorization was already rejecting the requests.

## Browser acceptance checklist for your machine

At 1440, 1024, 768 and 390 px: check navigation, catalog card grids, search/filter/empty states, course outlines, payment modal keyboard focus and scrolling, dashboard, lesson sidebar, player controls, and no horizontal overflow. Verify signup email/password setup, login/logout/reset and `/me` account edits. Check a real source video in Chrome, Firefox and Safari: play/pause/seek, saved position, grants renewed beyond five minutes, expired session, revoked enrollment, fullscreen/PiP watermark visibility and reduced-motion/keyboard behavior. Confirm native rich activities and assessment-gated completion still work.

No public site or production service was deployed. These tests are focused regression evidence, not a complete penetration test, accessibility audit, or load test.

## Docker startup corrections — 2026-10-14

User-run Docker logs revealed two bootstrap defects not covered by native tests: the named bench volume's root directory was not writable by the frappe user, and Bench's shallow clones omitted the pinned commit objects. Compose now performs a scoped one-time ownership initialization before starting the app. The bootstrap explicitly fetches missing pinned commits for Frappe, Payments and LMS before checkout. Shell syntax, Compose YAML parsing, and a regression test reproducing a missing commit in a depth-one clone passed. The regression also checks a second, idempotent run. A full Docker startup still cannot be executed in this assistant environment; the native test results above do not establish Docker compatibility.

### Interrupted-install lockfile correction — 2026-10-14

A later user-run Docker log showed that `bench get-app` ran Yarn before the pinned LMS checkout. Yarn changed `frontend/yarn.lock`, so Git correctly refused the checkout. The bootstrap now clones LMS and Payments without installing them, selects their pinned revisions, and only then calls `bench setup requirements frappe payments lms`. For an interrupted older bootstrap, it preserves changed tracked `yarn.lock` / `frontend/yarn.lock` files in a named Git stash before switching commits. Other tracked source edits cause a clear refusal, never an automatic reset or deletion. An already-selected pin is left untouched on repeat runs.

Four executable Git regression checks passed: missing shallow-clone commit retrieval; preserving generated lockfile contents in a stash and retaining subsequent edits on repeat runs; refusing to overwrite source edits; and checking all three selected revisions before the dependency-install phase. The last check uses real local Git repositories with a Bench command stub; it does not establish that a complete Docker installation succeeds. See bootstrap-test-results.txt.

### App registry repair and startup lifecycle — 2026-10-14

The next user log reached the custom app install, then failed importing
`lmsnightjar_learning`. Bench writes `sites/apps.txt` without a guaranteed final
newline; our former shell append merged two package names. The new bootstrap
normalizes complete lines, removes duplicate entries, backs up and repairs only
the known concatenation forms, and atomically replaces the registry. It preserves
unrelated app entries. Repair runs before any existing-bench commands and app
registration runs again after installation. Package/module-file checks now precede
database setup. Startup phases label errors without echoing credentials.

All nine bootstrap regressions pass. Five added cases cover no-final-newline
registration with an unrelated app retained; repair of the observed corruption
with an original-file backup; recovery through service-start invocation and a
second startup with no second site creation; interrupted build/retry without a
premature completion marker; and refusal to overwrite an incomplete site directory.
Shell syntax validation also passed.

The lifecycle checks execute the actual shell and Python filesystem logic against
temporary directories, with simulated Bench, package-manager and build commands.
They do NOT execute Frappe site creation, migrations, real asset builds, services,
or Docker. The earlier native integration results remain separate evidence. Full
Docker fresh-install/restart tests and fixed-image validation remain outstanding.

### Running the new focused suites

`scripts/unified_check.py` requires `NJ_RUN_INTEGRATION=1`, `FRAPPE_BENCH_ROOT`,
`NJ_TEST_SITE` (default `nightjar.localhost`), `NJ_TEST_ADMIN_PASSWORD`, and an
absolute `NJ_BROWSER_FIXTURE` JSON path. Run it with the bench environment Python.
`scripts/unified_browser.cjs` uses the same integration flag, administrator
password and fixture, plus `NJ_BASE_URL`; optional `PLAYWRIGHT_MODULE` and
`CHROMIUM_PATH` locate your QA browser installation. Both write result JSON to
the current working directory. Browser checks also write local screenshots.

For these suites the fixture contains `free` (published free course document
name), `lesson` (its first lesson), and `activity` (a lesson containing a native
quiz). The browser expects the quiz to offer a **Start Quiz** button, an **HTTPS**
answer radio, and **Submit**; configure that answer as correct and disable
per-question answer display. Use the supplied starter courses in a disposable
site, or adapt these fixture-specific assertions. These suites enable signup,
create users and learning records, and are unsuitable for a valuable database.
