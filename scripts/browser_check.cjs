const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs");
const path = require("path");
const assert = require("assert/strict");
const base = process.env.NJ_BASE_URL || "http://nightjar.localhost:8000";
if (
  process.env.NJ_RUN_INTEGRATION !== "1" ||
  !new URL(base).hostname.endsWith(".localhost")
)
  throw new Error(
    "Requires NJ_RUN_INTEGRATION=1 and a disposable .localhost site.",
  );
if (!process.env.NJ_TEST_ADMIN_PASSWORD || !process.env.NJ_BROWSER_FIXTURE)
  throw new Error(
    "Set NJ_TEST_ADMIN_PASSWORD and NJ_BROWSER_FIXTURE; see TEST-RESULTS.md.",
  );
(async () => {
  const browser = await chromium.launch({
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: path.resolve(process.env.CHROMIUM_PATH) }
      : {}),
    args: [
      "--no-sandbox",
      "--disable-gpu",
      "--no-zygote",
      "--host-resolver-rules=MAP nightjar.localhost 127.0.0.1",
    ],
    headless: true,
  });
  const context = await browser.newContext();
  const page = await context.newPage();
  const issues = [];
  page.on("pageerror", (e) => issues.push(e.message));
  for (let n = 0; n < 30; n++) {
    try {
      await page.goto(base + "/learn");
      break;
    } catch {
      await new Promise((r) => setTimeout(r, 200));
    }
  }
  const results = [];
  const pass = (test) => {
    results.push({ test, result: "PASS" });
    console.log("PASS", test);
  };
  await page.getByRole("heading", { name: "Find your next skill" }).waitFor();
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    pass("Catalog has no horizontal overflow at " + width + "px");
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".mobile-toggle").click();
  assert(await page.getByRole("navigation").isVisible());
  pass("Mobile navigation opens");
  await page.goto(base + "/login#signup");
  await page.waitForTimeout(1000);
  await page.locator("#signup_fullname").fill("Browser Student");
  await page
    .locator("#signup_email")
    .fill("browser-" + Date.now() + "@example.invalid");
  await page.locator(".form-signup button[type=submit]").click();
  await page
    .locator(".nightjar-signup-feedback")
    .filter({ hasText: "Your account was created" })
    .waitFor();
  pass("Native signup creates account and shows missing-email setup guidance");
  const signupURL = "**/api/method/frappe.core.doctype.user.user.sign_up";
  await page.route(signupURL, (route) =>
    route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ exc_type: "QueryTimeoutError" }),
    }),
  );
  await page.locator(".form-signup button[type=submit]").click();
  await page
    .getByRole("alert")
    .filter({ hasText: "database is busy" })
    .waitFor();
  assert(await page.locator(".form-signup button[type=submit]").isEnabled());
  pass("Signup server failure shows persistent inline error and enables retry");
  await page.unroute(signupURL);
  await page.route(signupURL, (route) => route.abort());
  await page.locator(".form-signup button[type=submit]").click();
  await page
    .getByRole("alert")
    .filter({ hasText: "connection was interrupted" })
    .waitFor();
  pass("Signup network failure explains uncertain outcome");
  await page.unroute(signupURL);
  await page.goto(base + "/login#login");
  await page.locator("#login_email").fill("Administrator");
  await page
    .locator("#login_password")
    .fill(process.env.NJ_TEST_ADMIN_PASSWORD);
  await page.locator(".form-login button[type=submit]").click();
  await page.waitForURL((url) => !url.pathname.includes("login"), {
    timeout: 20000,
  });
  pass("Administrator signs in through real login form");
  await page.goto(base + "/lms/settings/users/new");
  await page.getByPlaceholder("jane@doe.com").waitFor();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page
    .getByRole("alert")
    .filter({ hasText: "Enter a first name" })
    .waitFor();
  pass("Instructor form validates missing fields inline");
  const instructorEmail = "browser-teacher-" + Date.now() + "@example.invalid";
  await page.getByPlaceholder("jane@doe.com").fill(instructorEmail);
  await page.getByPlaceholder("Jane", { exact: true }).fill("Browser");
  await page.getByPlaceholder("Doe", { exact: true }).fill("Instructor");
  await page
    .getByRole("switch", { name: "Course Creator", exact: true })
    .click();
  const memberURL = "**/api/method/nightjar_learning.accounts.create_member";
  let memberRequests = 0;
  await page.route(memberURL, async (route) => {
    memberRequests++;
    await new Promise((r) => setTimeout(r, 200));
    await route.continue();
  });
  await page
    .getByRole("button", { name: "Save", exact: true })
    .evaluate((button) => {
      button.click();
      button.click();
    });
  await page
    .getByRole("status")
    .filter({ hasText: "Member created." })
    .waitFor();
  assert.equal(memberRequests, 1);
  pass(
    "Mobile instructor creation succeeds with one request despite repeated click",
  );
  assert(
    await page.getByRole("button", { name: "Save", exact: true }).isDisabled(),
  );
  pass("Successful instructor save remains visible and cannot be resubmitted");
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  pass("Mobile instructor form has no horizontal overflow");
  await page.unroute(memberURL);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.reload();
  await page.getByPlaceholder("jane@doe.com").fill(instructorEmail);
  await page.getByPlaceholder("Jane", { exact: true }).fill("Duplicate");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page
    .getByRole("alert")
    .filter({ hasText: "already has an account" })
    .waitFor();
  pass("Desktop instructor duplicate rejection is visible in form");
  await page.route(memberURL, (route) =>
    route.fulfill({ status: 500, contentType: "application/json", body: "{}" }),
  );
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page
    .getByRole("alert")
    .filter({ hasText: "Unable to confirm the save" })
    .waitFor();
  assert(
    await page.getByRole("button", { name: "Save", exact: true }).isEnabled(),
  );
  pass("Instructor server failure keeps form open and allows retry");
  await page.unroute(memberURL);
  await page.route(memberURL, (route) => route.abort());
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page
    .getByRole("alert")
    .filter({ hasText: "Unable to confirm the save" })
    .waitFor();
  pass("Instructor network failure keeps a readable inline error");
  await page.unroute(memberURL);
  await page.goto(base + "/learn");
  await page.route("**/api/method/nightjar_learning.api.catalog*", (route) =>
    route.fulfill({
      status: 500,
      contentType: "text/html",
      body: "Temporary upstream failure",
    }),
  );
  await page.reload();
  await page
    .getByRole("alert")
    .filter({ hasText: "unreadable response" })
    .waitFor();
  pass(
    "Catalog server failure shows actionable error instead of blank content",
  );
  await page.unroute("**/api/method/nightjar_learning.api.catalog*");
  await page.getByRole("button", { name: "Refresh this page" }).click();
  await page.getByRole("heading", { name: "Find your next skill" }).waitFor();
  pass("Catalog recovers using visible retry control");
  const fixture = JSON.parse(fs.readFileSync(process.env.NJ_BROWSER_FIXTURE));
  const studentContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  const studentPage = await studentContext.newPage();
  studentPage.on("pageerror", (e) => issues.push(e.message));
  await studentPage.goto(base + "/login#login");
  await studentPage.locator("#login_email").fill(fixture.email);
  await studentPage.locator("#login_password").fill(fixture.password);
  await studentPage.locator(".form-login button[type=submit]").click();
  await studentPage.waitForURL((url) => !url.pathname.includes("login"), {
    timeout: 20000,
  });
  pass("Student signs in through native login form");
  await studentPage.goto(
    base + "/learn#course=" + encodeURIComponent(fixture.free),
  );
  await studentPage.getByRole("button", { name: "Enroll for free" }).waitFor();
  assert(
    await studentPage.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  pass("Course detail fits phone viewport");
  await studentPage.getByRole("button", { name: "Enroll for free" }).click();
  await studentPage.getByRole("heading", { name: "Course contents" }).waitFor();
  pass("Student can enroll in a free course from the mobile UI");
  const video = studentPage.locator("video");
  await studentPage.waitForFunction(
    () => document.querySelector("video")?.readyState >= 2,
  );
  await video.evaluate((el) => {
    el.muted = true;
    return el.play();
  });
  await studentPage.waitForFunction(
    () => document.querySelector("video")?.currentTime > 0.5,
  );
  const heartbeat = studentPage.waitForResponse(
    (response) =>
      response.url().includes("/video.heartbeat") ||
      response.url().includes("nightjar_learning.video.heartbeat"),
  );
  await video.evaluate((el) => el.pause());
  assert((await heartbeat).ok());
  assert.equal(
    (await studentPage.locator(".watermark").textContent()).trim(),
    fixture.email,
  );
  pass(
    "Encrypted HLS plays in Chromium with account watermark and saved playback heartbeat",
  );
  const message = "Browser discussion " + Date.now();
  await studentPage.getByPlaceholder("What’s on your mind?").fill(message);
  await studentPage
    .getByRole("button", { name: "Post comment", exact: true })
    .click();
  await studentPage
    .locator(".comment .prose")
    .filter({ hasText: message })
    .waitFor();
  pass("Student can post a lesson comment and sees the saved comment");
  await studentPage
    .getByRole("button", { name: "Mark as complete", exact: true })
    .click();
  await studentPage
    .getByRole("button", { name: "✓ Lesson completed", exact: true })
    .waitFor();
  pass("Lesson completion updates visibly");
  for (const width of [320, 390, 768, 1440]) {
    await studentPage.setViewportSize({ width, height: 900 });
    assert(
      await studentPage.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    pass("Lesson layout has no horizontal overflow at " + width + "px");
  }
  await studentPage.setViewportSize({ width: 390, height: 844 });
  await studentPage.goto(base + "/learn#view=dashboard");
  await studentPage.locator(".course-card").first().waitFor();
  assert(
    await studentPage.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  pass("Enrolled course appears in responsive student dashboard");
  await studentPage.goto(
    base + "/learn#course=" + encodeURIComponent(fixture.paid),
  );
  await studentPage
    .getByRole("button", { name: "Request enrollment", exact: true })
    .click();
  const dialog = studentPage.getByRole("dialog");
  await dialog.waitFor();
  assert(
    await studentPage.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  assert.equal(
    await studentPage.evaluate(() => document.body.style.overflow),
    "hidden",
  );
  pass(
    "Payment request dialog fits phone viewport and locks background scrolling",
  );
  await studentPage.keyboard.press("Escape");
  assert.equal(await dialog.count(), 0);
  pass("Payment dialog closes with Escape");
  await studentPage
    .getByRole("button", { name: "Request enrollment", exact: true })
    .click();
  await studentPage
    .getByLabel("Payment details (required)")
    .fill("QA-browser-transfer-" + Date.now());
  await studentPage
    .getByRole("button", { name: "Send for verification" })
    .click();
  await dialog.waitFor({ state: "hidden" });
  assert(
    await studentPage
      .getByRole("button", { name: "Request enrollment", exact: true })
      .isVisible(),
  );
  pass("Payment request submits but does not grant paid access");
  await studentPage.goto(base + "/lms/settings/users/new");
  await studentPage.waitForURL('**/learn');
  pass("Student LMS entry redirects to Learn");
  await studentContext.close();
  assert.deepEqual(issues, []);
  pass("No uncaught browser JavaScript errors in tested flows");
  fs.writeFileSync(
    process.env.NJ_BROWSER_RESULTS || "browser-test-results.json",
    JSON.stringify(results, null, 2),
  );
  console.log("JS_ERRORS", issues);
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
