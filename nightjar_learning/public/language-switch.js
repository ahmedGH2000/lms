/* Shared Arabic/English preference for native Frappe, LMS, and Nightjar. */
(() => {
  const KEY = "nightjar-language";
  const valid = (value) => (String(value || "").toLowerCase().startsWith("ar") ? "ar" : String(value || "").toLowerCase().startsWith("en") ? "en" : null);
  const saved = valid(localStorage.getItem(KEY));
  const rendered = valid(document.documentElement.lang);
  const language = saved || rendered || "ar";
  localStorage.setItem(KEY, language);
  document.cookie = `nightjar_language=${language}; Path=/; Max-Age=31536000; SameSite=Lax`;
  document.documentElement.lang = language;
  document.documentElement.dir = language === "ar" ? "rtl" : "ltr";

  // Native Frappe/LMS boot code may update these attributes after shared web
  // includes run. Keep the persisted preference authoritative for accessibility
  // tools as well as visual layout.
  const enforceDocumentLanguage = () => {
    if (document.documentElement.lang !== language)
      document.documentElement.lang = language;
    const direction = language === "ar" ? "rtl" : "ltr";
    if (document.documentElement.dir !== direction)
      document.documentElement.dir = direction;
  };
  new MutationObserver(enforceDocumentLanguage).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["lang", "dir"],
  });

  const customArabic = { "Payment requests": "طلبات الدفع", "Student view": "واجهة الطالب" };
  function translateCustomLabels(root = document.body) {
    if (language !== "ar" || !root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const plain = node.nodeValue.trim();
      if (customArabic[plain]) node.nodeValue = node.nodeValue.replace(plain, customArabic[plain]);
    }
  }

  if (location.pathname === "/learn" || location.pathname.startsWith("/learn/")) return;

  async function choose(next) {
    if (next === language) return;
    const previous = language;
    localStorage.setItem(KEY, next);
    document.cookie = `nightjar_language=${next}; Path=/; Max-Age=31536000; SameSite=Lax`;
    try {
      const response = await fetch("/api/method/nightjar_learning.localization.set_language", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          ...(window.frappe?.csrf_token ? { "X-Frappe-CSRF-Token": window.frappe.csrf_token } : {}),
        },
        body: JSON.stringify({ language: next }),
      });
      if (!response.ok) throw new Error("language update failed");
      location.reload();
    } catch (error) {
      localStorage.setItem(KEY, previous);
      document.cookie = `nightjar_language=${previous}; Path=/; Max-Age=31536000; SameSite=Lax`;
      throw error;
    }
  }

  function mount() {
    if (document.querySelector(".nightjar-language-switch")) return;
    const control = document.createElement("div");
    control.className = "nightjar-language-switch";
    control.setAttribute("role", "group");
    control.setAttribute("aria-label", language === "ar" ? "اختيار اللغة" : "Choose language");
    for (const [code, label] of [["ar", "العربية"], ["en", "English"]]) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.dataset.active = String(code === language);
      button.setAttribute("aria-pressed", String(code === language));
      button.addEventListener("click", async () => {
        control.dataset.busy = "true";
        try { await choose(code); }
        catch { control.dataset.busy = "false"; }
      });
      control.append(button);
    }
    document.body.append(control);
    translateCustomLabels();
    new MutationObserver((changes) => {
      for (const change of changes)
        for (const node of change.addedNodes)
          translateCustomLabels(node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement);
    }).observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
})();
