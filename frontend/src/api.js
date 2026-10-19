export const boot = JSON.parse(
  document.getElementById("nightjar-boot")?.textContent ||
    '{"user":"Guest","roles":[]}',
);
export async function rpc(method, args = {}, write = false) {
  const path = "/api/method/nightjar_learning." + method;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);
  try {
    const r = await fetch(
      write ? path : path + "?" + new URLSearchParams(args),
      {
        signal: controller.signal,
        method: write ? "POST" : "GET",
        credentials: "same-origin",
        headers: write
          ? {
              "Content-Type": "application/json",
              "X-Frappe-CSRF-Token": boot.csrf_token,
            }
          : {},
        ...(write ? { body: JSON.stringify(args) } : {}),
      },
    );
    const d = await r.json().catch(() => null);
    if (!d)
      throw new Error(
        "The server returned an unreadable response. Check your connection and try again.",
      );
    if (!r.ok || d.exc) {
      let m =
        r.status === 401
          ? "Sign-in failed or your session expired. Check your credentials and sign in again."
          : r.status === 403
            ? "You do not have access. Check your enrollment or sign in again."
            : "The request failed. Please try again.";
      try {
        m = JSON.parse(JSON.parse(d._server_messages)[0]).message.replace(
          /<[^>]*>/g,
          "",
        );
      } catch {}
      if (["QueryTimeoutError", "QueryDeadlockError"].includes(d.exc_type))
        m = "The database is busy. Wait a moment and try again.";
      if (r.status === 429)
        m = "Too many requests. Please wait before trying again.";
      if (/Failed to get method for command nightjar_learning\./.test(m))
        m = "This feature is unavailable because the server update is incomplete. Please contact the administrator.";
      else if (r.status >= 500)
        m = "The service is temporarily unavailable. Please try again shortly. If this continues, contact the administrator.";
      throw new Error(m);
    }
    return d.message;
  } catch (error) {
    if (error.name === "AbortError" || error instanceof TypeError)
      throw new Error(
        write
          ? "The connection was interrupted. Your change may have been saved. Refresh to check before submitting again."
          : "Could not reach the server. Check your connection and try again.",
      );
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}
export const money = (c) =>
  c.paid_course
    ? `${c.currency || ""} ${Number(c.course_price || 0).toLocaleString()}`
    : "Free";
export const duration = (n) => (n ? `${Math.ceil(n / 60)} min` : "Lesson");
