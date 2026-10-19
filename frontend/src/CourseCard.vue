<script setup>
import { ref, watch } from "vue";
import { money } from "./api";
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
          course.category || "Build your skills"
        }}</span></template
      ><span class="level-chip">{{ course.nj_difficulty || "Beginner" }}</span>
    </div>
    <div class="card-copy">
      <div class="card-meta">
        <span>{{ course.category || "Development" }}</span
        ><span>{{ course.lessons || 0 }} lessons</span>
      </div>
      <h3>{{ course.title }}</h3>
      <p>{{ course.short_introduction }}</p>
      <div v-if="enrolled" class="card-progress">
        <div>
          <span>{{ Math.round(course.progress || 0) }}% complete</span
          ><span>Resume learning ↗</span>
        </div>
        <progress
          :value="course.progress || 0"
          max="100"
          :aria-label="course.title + ' progress'"
        ></progress>
      </div>
      <div v-else class="card-bottom">
        <span>{{ course.instructors?.[0]?.name || "Your instructor" }}</span
        ><strong>{{ money(course) }}</strong>
      </div>
    </div></a
  >
</template>
