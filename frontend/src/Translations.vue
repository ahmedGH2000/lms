<script setup>
import { onMounted, ref } from "vue";
import { rpc } from "./api";
import { t } from "./i18n";

const courses = ref([]), selected = ref(""), bundle = ref(null);
const busy = ref(false), loading = ref(true), error = ref(""), notice = ref("");

async function start() {
  loading.value = true;
  error.value = "";
  try {
    courses.value = await rpc("localization.translation_courses");
    if (courses.value.length) {
      selected.value = courses.value[0].name;
      await load();
    }
  } catch (e) { error.value = e.message; }
  finally { loading.value = false; }
}

async function load() {
  if (!selected.value) return;
  loading.value = true;
  error.value = "";
  notice.value = "";
  try { bundle.value = await rpc("localization.translation_bundle", { course: selected.value }); }
  catch (e) { error.value = e.message; }
  finally { loading.value = false; }
}

async function save() {
  if (busy.value || !bundle.value) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    const payload = {
      course: bundle.value.course.translations,
      chapters: bundle.value.chapters.map((chapter) => ({
        name: chapter.name,
        ...chapter.translations,
        lessons: chapter.lessons.map((lesson) => ({ name: lesson.name, ...lesson.translations })),
      })),
    };
    await rpc("localization.save_translation_bundle", { course: selected.value, payload }, true);
    notice.value = t("Translations saved.");
  } catch (e) { error.value = e.message; }
  finally { busy.value = false; }
}

onMounted(start);
</script>

<template>
  <section class="translation-editor">
    <div class="section-heading">
      <div><span class="intro-note">{{ t("Teaching studio") }}</span><h1>{{ t("Course translations") }}</h1>
      <p>{{ t("Add Arabic and English versions. Empty fields fall back to the other language, then the original content.") }}</p></div>
      <a class="text-button" href="/lms">{{ t("Teaching studio") }} ↗</a>
    </div>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <p v-if="notice" class="notice success" role="status">{{ notice }}</p>
    <label class="translation-course-select">{{ t("Choose a course") }}
      <select v-model="selected" :disabled="busy" @change="load">
        <option v-for="course in courses" :key="course.name" :value="course.name">{{ course.nj_title_ar || course.nj_title_en || course.title }}</option>
      </select>
    </label>
    <p v-if="loading" role="status">{{ t("Loading translations…") }}</p>
    <p v-else-if="!courses.length">{{ t("No courses are assigned to this account.") }}</p>
    <form v-else-if="bundle" @submit.prevent="save" class="translation-form">
      <section class="translation-unit">
        <h2>{{ bundle.course.original.title }}</h2>
        <p class="translation-original"><b>{{ t("Original") }}:</b> {{ bundle.course.original.short_introduction }}</p>
        <div class="translation-columns">
          <fieldset v-for="code in ['ar', 'en']" :key="code" :dir="code === 'ar' ? 'rtl' : 'ltr'">
            <legend>{{ t(code === 'ar' ? 'Arabic version' : 'English version') }}</legend>
            <label>{{ t("Title") }}<input v-model="bundle.course.translations[code].title" maxlength="140" /></label>
            <label>{{ t("Short introduction") }}<textarea v-model="bundle.course.translations[code].short_introduction" maxlength="500" /></label>
            <label>{{ t("Description") }}<textarea class="translation-long" v-model="bundle.course.translations[code].description" maxlength="100000" /></label>
          </fieldset>
        </div>
      </section>
      <section v-for="(chapter, chapterIndex) in bundle.chapters" :key="chapter.name" class="translation-unit">
        <h2>{{ t("Chapter") }} {{ chapterIndex + 1 }} · {{ chapter.original.title }}</h2>
        <div class="translation-columns compact">
          <fieldset v-for="code in ['ar', 'en']" :key="code" :dir="code === 'ar' ? 'rtl' : 'ltr'">
            <legend>{{ t(code === 'ar' ? 'Arabic version' : 'English version') }}</legend>
            <label>{{ t("Title") }}<input v-model="chapter.translations[code].title" maxlength="140" /></label>
          </fieldset>
        </div>
        <article v-for="lesson in chapter.lessons" :key="lesson.name" class="translation-lesson">
          <h3>{{ lesson.original.title }}</h3>
          <div class="translation-columns">
            <fieldset v-for="code in ['ar', 'en']" :key="code" :dir="code === 'ar' ? 'rtl' : 'ltr'">
              <legend>{{ t(code === 'ar' ? 'Arabic version' : 'English version') }}</legend>
              <label>{{ t("Title") }}<input v-model="lesson.translations[code].title" maxlength="140" /></label>
              <label>{{ t("Lesson body") }}<textarea class="translation-long" v-model="lesson.translations[code].body" maxlength="100000" /></label>
              <label>{{ t("Structured content") }}<textarea class="translation-code" v-model="lesson.translations[code].content" maxlength="500000" spellcheck="false" /></label>
            </fieldset>
          </div>
        </article>
      </section>
      <div class="translation-save"><button class="button" :disabled="busy">{{ busy ? t("Loading translations…") : t("Save translations") }}</button></div>
    </form>
  </section>
</template>
