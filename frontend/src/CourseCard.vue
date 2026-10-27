<script setup>
import { ref, watch } from "vue";
import { money } from "./api";
import { t } from "./i18n";
const props = defineProps({
  course: Object,
  index: { type: Number, default: 0 },
  enrolled: Boolean,
});
const imageFailed = ref(false);
watch(() => props.course.image, () => { imageFailed.value = false; });
const colors = ["blue", "violet", "teal", "amber", "rose", "sky"],
  symbols = ["{ }", "</>", "⌘", "[ ]", "λ", "→"];
</script>
<template>
  <a class="course-card" :href="`#course=${encodeURIComponent(course.name)}`"
    ><div class="course-art" :class="colors[index % 6]">
      <img
        v-if="course.image && !imageFailed"
        @error="imageFailed = true"
        :src="course.image"
        alt=""
        loading="lazy"
      /><template v-else
        ><i class="orbit one"></i><i class="orbit two"></i
        ><span class="art-symbol">{{ symbols[index % 6] }}</span
        ><span class="art-subject">{{
          course.category || t("Build your skills")
        }}</span></template
      ><span class="level-chip">{{ t(course.nj_difficulty || "Beginner") }}</span>
    </div>
    <div class="card-copy">
      <div class="card-meta">
        <span>{{ course.category || t("Development") }}</span
        ><span>{{ course.lessons || 0 }} {{ t("lessons") }}</span>
      </div>
      <h3 dir="auto">{{ course.title }}</h3>
      <p dir="auto">{{ course.short_introduction }}</p>
      <div v-if="enrolled" class="card-progress">
        <div>
          <span>{{ Math.round(course.progress || 0) }}% {{ t("complete") }}</span
          ><span>{{ t("Resume learning") }} ↗</span>
        </div>
        <progress
          :value="course.progress || 0"
          max="100"
          :aria-label="t('{course} progress', { course: course.title })"
        ></progress>
      </div>
      <div v-else class="card-bottom">
        <span>{{ course.instructors?.[0]?.name || t("Your instructor") }}</span
        ><strong>{{ money(course) }}</strong>
      </div>
    </div></a
  >
</template>
