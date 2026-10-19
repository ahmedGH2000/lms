<script setup>
import { ref, onMounted } from "vue";
import DOMPurify from "dompurify";
import { rpc, boot } from "./api";
const props = defineProps({ course: String });
const data = ref({ items: [] }),
  text = ref(""),
  rating = ref("5"),
  responses = ref({}),
  busy = ref(false),
  error = ref("");
const safe = (s) => DOMPurify.sanitize(s || "");
async function load() {
  data.value = await rpc("community.reviews", { course: props.course });
}
onMounted(() => run(load));
async function run(fn) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await fn();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function post() {
  run(async () => {
    await rpc(
      "community.review",
      { course: props.course, rating: rating.value, text: text.value },
      true,
    );
    text.value = "";
    await load();
  });
}
function reply(r) {
  run(async () => {
    await rpc(
      "community.respond",
      { review: r.name, text: responses.value[r.name] },
      true,
    );
    responses.value[r.name] = "";
    await load();
  });
}
function remove(kind, r) {
  if (!window.confirm("Remove this post?")) return;
  run(async () => {
    await rpc("community.remove", { kind, name: r.name }, true);
    await load();
  });
}
</script>
<template>
  <section class="reviews discussion">
    <div class="section-heading">
      <div>
        <h2>What students think</h2>
        <p>Course reviews and conversations with your instructor.</p>
      </div>
      <span>{{ data.items.length }} reviews</span>
    </div>
    <p v-if="error" role="alert" class="notice error">{{ error }}</p>
    <form
      v-if="data.can_review && !data.items.some((r) => r.is_mine)"
      class="stack-form"
      @submit.prevent="post"
    >
      <label
        >Your rating<select v-model="rating">
          <option v-for="n in 5" :value="String(n)">
            {{ n }} {{ n === 1 ? "star" : "stars" }}
          </option>
        </select></label
      ><label
        >Your review<textarea
          v-model="text"
          required
          maxlength="4000"
          placeholder="What helped you learn?"
        /></label
      ><button class="button" :disabled="busy">Post review</button>
    </form>
    <p v-if="!data.items.length">
      No reviews yet. Be the first to share your experience after enrolling.
    </p>
    <article v-for="r in data.items" :key="r.name" class="review-card">
      <header class="comment-author">
        <span class="avatar">{{ r.author[0] }}</span
        ><b>{{ r.author }}</b
        ><span
          class="stars"
          :aria-label="Math.round(r.rating * 5) + ' out of 5 stars'"
          >{{ "★".repeat(Math.round(r.rating * 5))
          }}{{ "☆".repeat(5 - Math.round(r.rating * 5)) }}</span
        >
      </header>
      <div class="prose" v-html="safe(r.review)"></div>
      <button
        v-if="data.can_moderate"
        class="text-button"
        :disabled="busy"
        @click="remove('review', r)"
      >
        Delete review
      </button>
      <blockquote v-if="r.nj_response" class="review-response">
        <b>{{ r.responder }} <span class="instructor-tag">Instructor</span></b>
        <div class="prose" v-html="safe(r.nj_response)"></div>
        <button
          v-if="data.can_moderate"
          class="text-button"
          :disabled="busy"
          @click="remove('review_reply', r)"
        >
          Delete reply
        </button>
      </blockquote>
      <form v-if="data.can_reply" class="stack-form" @submit.prevent="reply(r)">
        <label
          >{{ r.nj_response ? "Replace your reply" : "Reply as instructor"
          }}<textarea
            v-model="responses[r.name]"
            required
            maxlength="4000"
          /></label
        ><button class="button small" :disabled="busy">
          Post instructor reply
        </button>
      </form>
    </article>
  </section>
</template>
