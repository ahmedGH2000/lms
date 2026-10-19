/* Enhance the native signup forms without replacing Frappe authentication. */
(() => {
  function setup() {
    if (location.pathname !== "/login") return;
    document.querySelectorAll(".form-signup, .signup-form").forEach((form) => {
      const feedback =
        form.querySelector(".nightjar-signup-feedback") ||
        document.createElement("div");
      feedback.className = "nightjar-signup-feedback";
      feedback.setAttribute("role", "status");
      feedback.setAttribute("tabindex", "-1");
      form.append(feedback);
      let busy = false;
      // Stop the native handler on this form only; use its same server method.
      window
        .jQuery(form)
        .off("submit")
        .on("submit.nightjar", async (event) => {
          event.preventDefault();
          if (busy) return;
          const email = form.querySelector("#signup_email");
          const name = form.querySelector("#signup_fullname");
          const button = form.querySelector("button[type=submit]");
          const terms = form.querySelector("#signup-terms");
          const category = form.querySelector("#user_category");
          const show = (message, error = false) => {
            feedback.textContent = message;
            feedback.dataset.error = String(error);
            feedback.setAttribute("role", error ? "alert" : "status");
            feedback.focus();
          };
          if (
            !name?.value.trim() ||
            !email?.value.trim() ||
            !email.checkValidity()
          ) {
            show("Enter your full name and a valid email address.", true);
            return;
          }
          if ((terms && !terms.checked) || (category && !category.value)) {
            show(
              "Complete the required category and accept the terms before signing up.",
              true,
            );
            return;
          }
          busy = true;
          const label = button.textContent;
          button.disabled = true;
          button.textContent = "Creating account…";
          form.setAttribute("aria-busy", "true");
          show("Creating your account. Please wait…");
          const custom = form.classList.contains("signup-form");
          const method = custom
            ? "lms.lms.user.sign_up"
            : "frappe.core.doctype.user.user.sign_up";
          const args = {
            email: email.value.trim(),
            full_name: name.value.trim(),
            redirect_to: "/learn",
            verify_terms: terms?.checked ? 1 : 0,
            user_category: category?.value || "",
          };
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), 65000);
          try {
            const response = await fetch("/api/method/" + method, {
              method: "POST",
              credentials: "same-origin",
              signal: controller.signal,
              headers: {
                "Content-Type": "application/json",
                ...(window.frappe?.csrf_token
                  ? { "X-Frappe-CSRF-Token": frappe.csrf_token }
                  : {}),
              },
              body: JSON.stringify(args),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || data.exc) {
              let message =
                response.status === 429
                  ? "Too many attempts. Please wait before trying again."
                  : "Account creation failed. Please try again or contact the administrator.";
              if (
                ["QueryTimeoutError", "QueryDeadlockError"].includes(
                  data.exc_type,
                )
              ) {
                message =
                  "The database is busy and could not finish signing you up. Wait a moment and try again.";
              } else {
                try {
                  const entry = JSON.parse(data._server_messages)[0];
                  const text =
                    typeof entry === "string"
                      ? JSON.parse(entry).message
                      : entry.message;
                  const parsed = new DOMParser().parseFromString(
                    text,
                    "text/html",
                  );
                  message = parsed.body.textContent || message;
                } catch {}
              }
              show(message, true);
            } else if (!Array.isArray(data.message)) {
              show(
                "The server returned an unexpected response. Check your email before trying again.",
                true,
              );
            } else {
              const [code, message] = data.message;
              show(
                Number(code) === 2
                  ? "Your account was created, but no setup email was sent. Ask the administrator to configure outgoing email and send your password setup link."
                  : message,
                Number(code) === 0,
              );
            }
          } catch {
            show(
              "The connection was interrupted. The account may have been created. Check your email or try signing in before submitting again.",
              true,
            );
          } finally {
            clearTimeout(timeout);
            busy = false;
            button.disabled = false;
            button.textContent = label;
            form.removeAttribute("aria-busy");
          }
        });
    });
  }
  // Frappe emits this after binding the original forms.
  window.jQuery?.(document).on("login_rendered", setup);
  window.frappe?.ready(() => setTimeout(setup, 0));
})();
