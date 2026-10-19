# Security model and remaining work

## Implemented boundary

Frappe owns authentication, sessions, CSRF and role identity. Nightjar never accepts a caller-supplied student identity for learner actions. Protected lesson, discussion and playback requests resolve membership from the session, require an enabled account, verify the actual lesson/course relationship, and check native prerequisite locks. Paid access requires approved manual payment, a received native course payment, or an explicit administrator grant plus enrollment. Assigned instructors and System Managers have staff access. Generic Frappe document/list endpoints are restricted alongside the custom APIs.

Payment requests snapshot the server-side course quote. Student writes cannot verify payment or mutate request identity. Pending → Approved/Rejected and Approved → Revoked transitions require a System Manager and review note in the review API. Course/request locking prevents duplicate requests/enrollments through that API. Approvals and enrollment writes share a transaction. Administrative database/Desk access is trusted; an administrator can intentionally grant or change records.

Future gateway adapters must run on the server, verify the provider signature and settled status, bind course/member/amount/currency, enforce a unique event/payment ID, and handle refunds and replay. The `nightjar_verified_gateway` server flag exists only for trusted Python adapters; no browser endpoint sets it. Existing native gateway paths may need adaptation and tests before enabling them. Do not treat callback parameters or a checkout redirect as proof of payment.

## Video authorization

Media stays outside public web roots. FFmpeg encrypts HLS segments with AES-128. A five-minute HMAC grant includes account, hash of session ID, lesson, asset, issued time and expiry. Its secret comes from the environment. The resource endpoint checks the live session and current enrollment for every manifest, key and segment. Revoked enrollment therefore invalidates a still-unexpired grant on the next request. Realpath containment plus strict UUID/filename allowlists prevent directory traversal and symlink escapes.

Keys/manifests/segments are `private, no-store`; tokenized endpoint logging is disabled in the NGINX example. TLS, log redaction and proxy cache policy must also be enforced at every outer proxy. Protect application/APM/error logs from recording query-string grants. Do not enable cross-origin credential access. The optional NGINX location is `internal` and permits only segment filenames; it never serves encryption keys publicly.

The visible watermark contains the signed-in account identifier and moves during playback, including the Shaka container's fullscreen mode. Resume telemetry is finite/range checked, member scoped, and rate limited. Grant and heartbeat events are retained 30 days when the Frappe daily scheduler is enabled. Completion is handled by native lesson rules, not by trusting a claimed playback time.

## Limits

AES-HLS with authenticated key delivery is **access control, not hardware-backed DRM**. An authorized browser receives decrypted video and its key. A determined user can extract them, save segments, remove the DOM watermark, or record the screen. A single asset key is reused across its renditions/segments in this implementation. A watermark deters casual sharing but is not forensic attribution. Client-reported playback is not proof that someone watched a lesson. Buffered/downloaded content cannot be recalled when enrollment is revoked.

This system does not promise prevention of piracy or screen recording. It uses no paid DRM service.

## Before a public launch

1. Run browser playback/resume/renewal tests in Chrome, Firefox and Safari; test mobile native fullscreen/PiP watermark behavior and accessibility. Some OS fullscreen modes may exclude HTML overlays.
2. Review the full installed LMS/Frappe API surface, including batches, reports, files, notes, integrations and server scripts. This app adds gates to the tested lesson/enrollment/payment/discussion paths; it is not an audit of every upstream feature. Disable unused integrations and public original media URLs.
3. Run dependency/advisory review on upstream Python and Node dependencies. The custom UI production dependency audit was clean at delivery, which is not a guarantee of absence of vulnerabilities.
4. Configure TLS, secure cookies, least-privilege database/media users, secret rotation, request limits, log retention, monitoring, backups and tested restores. Use a secret manager for production. Rotate signing secrets after exposure; old grants will fail immediately.
5. Keep developer mode off in production. Configure email verification/reset and administrator MFA. Add automated deployment regression gates and load/concurrency tests. Audit admin grants and payment reconciliation.
6. Review the privacy implications of displaying an email/account identifier and retaining playback events; choose a suitable account identifier policy before launch.

No public deployment or publication was performed.

## Unified account/community update

Public registration creates only Website Users with the LMS Student role. Client-supplied roles are ignored. Native signup-disable policy, hourly creation limits, rate limits, password policy, and session/CSRF controls apply. Custom registration requires 12–128 characters and confirmation. No password is returned to the UI or stored in project files. Email ownership is not verified in this initial workflow.

Profile updates always target the session user and allow only first name, last name and bio. Administrators can set Website User passwords through the Students page; staff password management remains in Desk. Self-service changes require the current password or a native expiring reset token. Native login and reset functions retain password hashing, lockout and two-factor policy.

Review creation checks current paid entitlement and native enrollment. Only assigned instructors/System Managers can reply to a review. Removal endpoints require System Manager/Administrator, not a client-supplied role. HTML is escaped on write and sanitized on render. Review-response custom fields are read-only and guarded against generic student edits. Native quiz read/answer/submission API adapters also check live course entitlement and prerequisite access.

Navigation redirects are a UX feature, not a permission boundary. Embedded resources still require server-side authorization. Do not assume the resource adapter is an audit of every native attachment, assignment, SCORM or plugin endpoint.
