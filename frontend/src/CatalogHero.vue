<script setup>
import PyramidMark from "./PyramidMark.vue";
import { t } from "./i18n";
defineProps({ signedIn: Boolean });
function browse() {
  const target = document.getElementById("course-browser");
  target?.focus({ preventScroll: true });
  target?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" });
}
</script>

<template>
  <section class="learning-hero">
    <div class="learning-hero-copy">
      <h1>{{ t("Less watching. More understanding.") }}</h1>
      <p>{{ t("Practical courses. Thoughtful explanations. Real progress.") }} {{ t("Find your next course and keep moving forward.") }}</p>
      <div class="hero-actions">
        <button class="button" type="button" @click="browse">{{ t("Find a course") }}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 4v16m-6-6 6 6 6-6"/></svg></button>
        <a :href="signedIn ? '#view=dashboard' : '#view=signup'">{{ t(signedIn ? "My learning" : "Create an account") }}</a>
      </div>
    </div>
    <PyramidMark />
  </section>
</template>

<style scoped>
.learning-hero { display: grid; grid-template-columns: minmax(0,1.2fr) minmax(320px,.8fr); gap: 40px; align-items: center; padding: 48px 0 56px; min-height: 485px; }
.learning-hero-copy { padding-block: 16px; }
.learning-hero h1 { font-size: clamp(46px,5.5vw,76px); line-height: 1.04; letter-spacing: -.045em; max-width: 760px; margin-bottom: 26px; text-wrap: balance; }
.learning-hero p { font-size: 18px; line-height: 1.75; max-width: 510px; margin-bottom: 30px; }
.hero-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 26px; }
.hero-actions .button { gap: 20px; min-height: 50px; }
.hero-actions svg { width: 20px; height: 20px; }
.hero-actions > a { padding-block: 14px; font-size: 15px; color: #d0e5f7; border-bottom: 1px solid #577086; }
.hero-actions > a:hover { color: #fff; border-color: #b9e4ff; }
:global(html[dir="rtl"]) .learning-hero h1 { letter-spacing: 0; line-height: 1.32; font-size: clamp(42px,5.2vw,68px); }
@media (max-width: 900px) { .learning-hero { grid-template-columns: minmax(0,1fr) minmax(260px,.7fr); gap: 12px; } .learning-hero h1 { font-size: 54px; } }
@media (max-width: 760px) {
  .learning-hero { grid-template-columns: 1fr; padding: 22px 0 30px; gap: 8px; }
  .learning-hero h1 { font-size: clamp(40px,11vw,58px); max-width: 540px; margin-bottom: 20px; }
  .learning-hero p { font-size: 16px; margin-bottom: 22px; }
  :global(html[dir="rtl"]) .learning-hero h1 { font-size: clamp(38px,10.5vw,54px); }
  .hero-actions { gap: 10px 20px; }
}
</style>
