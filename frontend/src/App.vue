<script setup>
import {
  ref,
  computed,
  watch,
  onMounted,
  onBeforeUnmount,
  defineAsyncComponent,
  nextTick,
} from "vue";
import DOMPurify from "dompurify";
import { marked } from "marked";
import { rpc, boot, money, duration } from "./api";
import CourseCard from "./CourseCard.vue";
import CatalogHero from "./CatalogHero.vue";
import Notice from "./Notice.vue";
import AccountPanel from "./AccountPanel.vue";
import Reviews from "./Reviews.vue";
import Members from "./Members.vue";
import { language, setLanguage, t } from "./i18n";
const Player = defineAsyncComponent(() => import("./Player.vue"));
const Translations = defineAsyncComponent(() => import("./Translations.vue"));
const route = ref({}),
  courses = ref([]),
  categories = ref([]),
  total = ref(0),
  mine = ref([]),
  requests = ref([]),
  course = ref(null),
  lesson = ref(null),
  comments = ref([]);
const search = ref(""),
  category = ref(""),
  level = ref(""),
  page = ref(0),
  loading = ref(true),
  busy = ref(false),
  error = ref(""),
  notice = ref(""),
  mobile = ref(false);
const commentText = ref(""),
  replyTo = ref(null),
  paymentOpen = ref(false),
  paymentRef = ref(""),
  paymentFile = ref(null);
const signedIn = boot.user !== "Guest",
  compatible = boot.api_contract === 2,
  admin =
    boot.user === "Administrator" || boot.roles.includes("System Manager"),
  staff =
    admin ||
    boot.roles.some((x) => ["Course Creator", "Moderator"].includes(x));
const view = computed(
    () => route.value.view || (route.value.course ? "course" : "catalog"),
  ),
  firstName = computed(() => boot.full_name?.split(" ")[0] || "Learner");
const allLessons = computed(
    () => course.value?.chapters.flatMap((c) => c.lessons) || [],
  );
const safe = (v) =>
  DOMPurify.sanitize(v || "", {
    FORBID_TAGS: ["iframe", "style", "form"],
    FORBID_ATTR: ["style"],
  });
const markdown = (v) => safe(marked.parse(v || ""));
const blocks = computed(() => {
  try {
    return JSON.parse(lesson.value?.content || "{}").blocks || [];
  } catch {
    return [];
  }
});
const activityHeight = ref(650);
const hasActivity = computed(
  () =>
    !!lesson.value &&
    (Boolean(lesson.value.youtube || lesson.value.quiz_id) ||
      /\{\{\s*(Quiz|Video|YouTubeVideo|Audio|PDF|Embed)/.test(
        lesson.value.body || "",
      ) ||
      blocks.value.some(
        (b) => !["paragraph", "header", "code"].includes(b.type),
      )),
);
function activityMessage(e) {
  const frame = document.getElementById("lesson-activity");
  if (
    e.origin === location.origin &&
    e.source === frame?.contentWindow &&
    e.data?.type === "nightjar-activity-height"
  )
    activityHeight.value = Math.min(
      20000,
      Math.max(400, Number(e.data.height) || 650),
    );
}
function removeComment(c) {
  if (!window.confirm(t("Remove this comment? Replies will remain visible.")))
    return;
  act(async () => {
    await rpc("community.remove", { kind: "comment", name: c.name }, true);
    comments.value = await rpc("api.discussion", { lesson: lesson.value.name });
    notice.value = t("Comment removed.");
  });
}
function refreshPage() { location.reload(); }
function chooseLanguage(value) { act(() => setLanguage(value)); }
function documentFocus() {
  document.getElementById("main")?.focus();
}
let timer,
  seq = 0,
  routeSeq = 0,
  previousFocus;
const catalogLoading = ref(false), catalogError = ref(""), catalogReady = ref(false);
async function catalog() {
  if (view.value !== "catalog" || !compatible) return;
  const n = ++seq;
  catalogLoading.value = true;
  catalogError.value = "";
  try {
    const d = await rpc("api.catalog", {
      search: search.value,
      category: category.value,
      level: level.value,
      start: page.value * 24,
    });
    if (n !== seq) return;
    courses.value = d.courses;
    categories.value = d.categories;
    total.value = d.total;
    catalogReady.value = true;
  } catch (e) {
    if (n === seq && view.value === "catalog") catalogError.value = e.message;
  } finally {
    if (n === seq) catalogLoading.value = false;
  }
}
async function load() {
  clearTimeout(timer);
  ++seq; // Ignore catalog replies from the previous screen/filter state.
  const n = ++routeSeq;
  route.value = Object.fromEntries(new URLSearchParams(location.hash.slice(1)));
  document.documentElement.dataset.nightjarView = view.value;
  mobile.value = false;
  error.value = "";
  notice.value = "";
  loading.value = true;
  lesson.value = null;
  course.value = null;
  paymentOpen.value = false;
  replyTo.value = null;
  if (!compatible) { loading.value = false; return; }
  try {
    if (route.value.course) {
      const c = await rpc("api.course_detail", { course: route.value.course });
      if (n !== routeSeq) return;
      course.value = c;
      if (route.value.lesson) {
        const l = await rpc("api.lesson_detail", {
          lesson: route.value.lesson,
        });
        if (n !== routeSeq) return;
        if (l.course !== c.name)
          throw new Error(t("This lesson belongs to another course."));
        lesson.value = l;
        comments.value = await rpc("api.discussion", { lesson: l.name });
      }
    } else if (view.value === "dashboard" && signedIn) {
      mine.value = await rpc("api.dashboard");
      requests.value = await rpc("payments.requests");
    } else if (view.value === "payments" && staff)
      location.assign("/lms/payment-requests");
    else if (view.value === "catalog") await catalog();
  } catch (e) {
    if (n === routeSeq) error.value = e.message;
  } finally {
    if (n === routeSeq) loading.value = false;
  }
}
async function act(fn) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    await fn();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
function resume() {
  const id =
    course.value.enrollment?.current_lesson || allLessons.value[0]?.name;
  if (id)
    location.hash = `course=${encodeURIComponent(course.value.name)}&lesson=${encodeURIComponent(id)}`;
}
function enroll() {
  if (!signedIn) {
    location.hash = "view=login";
    return;
  }
  if (course.value.paid_course) {
    paymentOpen.value = true;
    return;
  }
  act(async () => {
    await rpc("payments.enroll", { course: course.value.name }, true);
    course.value = await rpc("api.course_detail", {
      course: course.value.name,
    });
    resume();
  });
}
function chooseReceipt(event) {
  error.value = "";
  const file = event.target.files?.[0];
  paymentFile.value = null;
  if (!file) return;
  if (!/\.(jpe?g|png|pdf)$/i.test(file.name) || !file.size || file.size > 10 * 1024 * 1024) {
    error.value = t("Choose one JPG, PNG, or PDF receipt no larger than 10 MB.");
    event.target.value = "";
    return;
  }
  paymentFile.value = file;
}
function closePayment() { if (!busy.value) paymentOpen.value = false; }
function sendPayment() {
  act(async () => {
    const data = new FormData();
    data.set("course", course.value.name);
    data.set("reference", paymentRef.value.trim());
    if (paymentFile.value) data.set("receipt", paymentFile.value);
    const result = await rpc("payments.request_payment", data, true);
    paymentRef.value = "";
    paymentFile.value = null;
    if (result.existing) {
      paymentOpen.value = false;
      notice.value = t("You already have a request for this course. Check its status in My learning; no new receipt was saved.");
      return;
    }
    paymentOpen.value = false;
    notice.value =
      t("Request received. Your instructor or administrator will verify payment before granting access.");
  });
}
function sendComment() {
  act(async () => {
    await rpc(
      "api.comment",
      {
        lesson: lesson.value.name,
        text: commentText.value,
        reply_to: replyTo.value?.name || null,
      },
      true,
    );
    commentText.value = "";
    replyTo.value = null;
    comments.value = await rpc("api.discussion", { lesson: lesson.value.name });
    notice.value = t("Your comment was posted.");
  });
}
function complete() {
  act(async () => {
    const d = await rpc("api.complete", { lesson: lesson.value.name }, true);
    lesson.value.complete = d.complete;
    course.value.enrollment = {
      ...course.value.enrollment,
      progress: d.progress,
    };
    notice.value = d.complete
      ? t("Lesson completed. Your progress is saved.")
      : t("Complete the required lesson activities first, then refresh your progress.");
  });
}

function trap(e) {
  if (e.key !== "Tab") return;
  const a = [
    ...e.currentTarget.querySelectorAll(
      "button:not(:disabled),input,textarea,a[href]",
    ),
  ];
  if (e.shiftKey && document.activeElement === a[0]) {
    e.preventDefault();
    a.at(-1)?.focus();
  } else if (!e.shiftKey && document.activeElement === a.at(-1)) {
    e.preventDefault();
    a[0]?.focus();
  }
}
watch(paymentOpen, async (open) => {
  document.body.style.overflow = open ? "hidden" : "";
  if (open) {
    paymentFile.value = null;
    previousFocus = document.activeElement;
    await nextTick();
    document.getElementById("payment-reference")?.focus();
  } else previousFocus?.focus?.();
});
watch(error, async (message) => {
  if (!message || paymentOpen.value) return;
  await nextTick();
  document.getElementById("action-error")?.focus();
});
watch([search, category, level], () => {
  ++seq;
  clearTimeout(timer);
  if (page.value !== 0) page.value = 0;
  else timer = setTimeout(catalog, 250);
});
watch(page, () => { ++seq; clearTimeout(timer); timer = setTimeout(catalog, 250); });
onMounted(() => {
  window.addEventListener("hashchange", load);
  window.addEventListener("message", activityMessage);
  load();
});
onBeforeUnmount(() => {
  document.body.style.overflow = "";
  clearTimeout(timer);
  window.removeEventListener("hashchange", load);
  window.removeEventListener("message", activityMessage);
});
</script>
<template>
  <a class="skip-link" href="#main" @click.prevent="documentFocus"
    >{{ t("Skip to content") }}</a
  >
  <header class="site-header" :inert="paymentOpen">
    <div class="header-inner">
      <a class="brand" href="#"
        ><svg viewBox="0 0 40 40" aria-hidden="true">
          <path d="M4 9 20 16 36 9 30 28 20 34 10 28Z" fill="currentColor" />
          <path
            d="m11 18 7 3-5 3m16-6-7 3 5 3"
            fill="none"
            stroke="#071021"
            stroke-width="3"
          /></svg
        >nightjar<span>learning</span></a
      ><button
        class="mobile-toggle quiet"
        @click="mobile = !mobile"
        :aria-expanded="mobile"
        :aria-label="t('Toggle navigation')"
        aria-controls="main-navigation"
      >
        ☰
      </button>
      <nav
        id="main-navigation"
        :class="{ open: mobile }"
        :aria-label="t('Main navigation')"
      >
        <a href="#" :class="{ active: view === 'catalog' }">{{ t("Explore courses") }}</a
        ><a href="#view=dashboard" :class="{ active: view === 'dashboard' }"
          >{{ t("My learning") }}</a
        ><a v-if="staff" href="/lms">{{ t("Teaching studio") }} ↗</a
        ><a v-if="staff" href="/lms/payment-requests">{{ t("Payments") }}</a
        ><a v-if="staff" href="#view=translations">{{ t("Translations") }}</a
        ><a v-if="admin" href="#view=members">{{ t("Students") }}</a
        ><a v-if="!signedIn" class="mobile-account-link" href="#view=login">{{ t("Sign in") }}</a
        ><a v-else class="mobile-account-link" href="#view=profile">{{ t("Profile") }}</a>
      </nav>
      <div class="language-switch" role="group" :aria-label="t('Choose language')">
        <button type="button" :aria-pressed="language === 'ar'" :class="{ active: language === 'ar' }" @click="chooseLanguage('ar')">العربية</button>
        <button type="button" :aria-pressed="language === 'en'" :class="{ active: language === 'en' }" @click="chooseLanguage('en')">English</button>
      </div>
      <a v-if="!signedIn" class="button small" href="#view=login">{{ t("Sign in") }}</a
      ><a
        v-else
        class="account"
        href="#view=profile"
        :aria-label="t('Manage account for {name}', { name: boot.full_name })"
        ><span>{{ firstName[0] }}</span
        ><b>{{ firstName }}</b></a
      >
    </div>
  </header>
  <main id="main" class="main-shell" tabindex="-1" :inert="paymentOpen">
    <Notice id="action-error" tabindex="-1" :message="paymentOpen ? '' : error" kind="error" @dismiss="error = ''" />
    <Notice :message="notice" @dismiss="notice = ''" />
    <div v-if="!compatible" class="empty" role="alert">
      <h2>{{ t("A platform update needs to finish.") }}</h2>
      <p>{{ t("Please contact the administrator, or refresh after the update is complete.") }}</p>
      <button class="button" @click="refreshPage">{{ t("Refresh page") }}</button>
    </div>
    <div v-else-if="loading" class="loading" role="status">
      <i></i>{{ t("Opening your learning space…") }}
    </div>
    <AccountPanel
      v-else-if="
        ['login', 'signup', 'forgot', 'reset', 'profile'].includes(view)
      "
      :key="view"
      :mode="view"
    />
    <Members v-else-if="view === 'members' && admin" />
    <Translations v-else-if="view === 'translations' && staff" />
    <template v-else-if="view === 'catalog'"
      ><CatalogHero :signed-in="signedIn" />
      <section id="course-browser" class="catalog-section course-browser" tabindex="-1" :aria-label="t('Explore courses')">
        <div class="section-heading">
          <div>
            <h2>{{ t("Find your next skill") }}</h2>
            <p>{{ t("Choose something worth your curiosity.") }}</p>
          </div>
          <span v-if="catalogReady && !catalogError && !catalogLoading" class="count">{{ total }} {{ t("courses") }}</span>
        </div>
        <div class="filters">
          <label class="search-field"
            ><svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg
            ><input
              v-model="search"
              type="search"
              :placeholder="t('What do you want to learn?')"
              :aria-label="t('Search courses')" /></label
          ><label
            ><span class="sr-only">{{ t("Category") }}</span
            ><select v-model="category">
              <option value="">{{ t("All topics") }}</option>
              <option v-for="c in categories" :key="c">{{ c }}</option>
            </select></label
          ><label
            ><span class="sr-only">{{ t("Difficulty") }}</span
            ><select v-model="level">
              <option value="">{{ t("All levels") }}</option>
              <option value="Beginner">{{ t("Beginner") }}</option>
              <option value="Intermediate">{{ t("Intermediate") }}</option>
              <option value="Advanced">{{ t("Advanced") }}</option>
            </select></label
          >
        </div>
        <div v-if="catalogError" class="empty" role="alert">
          <h3>{{ t("We couldn't load the courses.") }}</h3>
          <p>{{ catalogError }}</p>
          <button class="button" :disabled="catalogLoading" @click="catalog">{{ t("Retry loading courses") }}</button>
        </div>
        <div v-else-if="catalogLoading" class="loading" role="status">{{ t("Loading courses…") }}</div>
        <div v-else-if="courses.length" class="course-grid">
          <CourseCard
            v-for="(c, i) in courses"
            :key="c.name"
            :course="c"
            :index="i"
          />
        </div>
        <div v-if="catalogReady && !catalogError && !catalogLoading && !courses.length" class="empty">
          <h3>
            {{
              search || category || level
                ? t("No matching courses.")
                : t("Your learning library starts here.")
            }}
          </h3>
          <p>
            {{
              search || category || level
                ? t("Try another topic or clear your filters.")
                : t("Publish your first course in the teaching studio.")
            }}
          </p>
          <button
            v-if="search || category || level"
            class="button"
            @click="
              search = '';
              category = '';
              level = '';
            "
          >
            {{ t("Clear filters") }}</button
          ><a v-else-if="staff" class="button" href="/lms"
            >{{ t("Open teaching studio") }}</a
          >
        </div>
        <div v-if="!catalogError && !catalogLoading && total > 24" class="pagination">
          <button class="quiet" :disabled="!page" @click="page--">
            {{ t("Previous") }}</button
          ><span>{{ t("Page") }} {{ page + 1 }}</span
          ><button
            class="quiet"
            :disabled="(page + 1) * 24 >= total"
            @click="page++"
          >
            {{ t("Next") }}
          </button>
        </div>
      </section>
      <aside v-if="!signedIn" class="join-strip">
        <div>
          <h2>{{ t("Your next chapter starts with one lesson.") }}</h2>
          <p>{{ t("Create an account to save progress and join the conversation.") }}</p>
        </div>
        <a class="button" href="#view=signup">{{ t("Create an account") }}</a>
      </aside></template
    >
    <template v-else-if="view === 'dashboard'"
      ><section class="page-intro">
        <span class="intro-note">{{ t("Your learning space") }}</span>
        <h1>
          {{
            signedIn
              ? t("Keep going, {name}.", { name: firstName })
              : t("A place for your progress.")
          }}
        </h1>
        <p>{{ t("Pick up where you left off. Every lesson brings you closer.") }}</p>
      </section>
      <template v-if="signedIn"
        ><div class="stats">
          <div>
            <strong>{{ mine.length }}</strong
            ><span>{{ t("Enrolled courses") }}</span>
          </div>
          <div>
            <strong>{{ mine.filter((c) => c.progress >= 100).length }}</strong
            ><span>{{ t("Courses completed") }}</span>
          </div>
          <div>
            <strong
              >{{
                mine.length
                  ? Math.round(
                      mine.reduce((s, c) => s + c.progress, 0) / mine.length,
                    )
                  : 0
              }}%</strong
            ><span>{{ t("Average course progress") }}</span>
          </div>
        </div>
        <div class="section-heading">
          <h2>{{ t("Continue learning") }}</h2>
          <a class="text-button" href="#">{{ t("Explore more courses") }} ↗</a>
        </div>
        <div class="course-grid">
          <CourseCard
            v-for="(c, i) in mine"
            :key="c.name"
            :course="c"
            :index="i"
            enrolled
          />
        </div>
        <div v-if="!mine.length" class="empty">
          <h3>{{ t("Find something you’re curious about.") }}</h3>
          <p>{{ t("Your enrolled courses will appear here.") }}</p>
          <a class="button" href="#">{{ t("Explore courses") }}</a>
        </div>
        <section v-if="requests.length" class="request-section">
          <h2>{{ t("Payment requests") }}</h2>
          <div v-for="r in requests" :key="r.name" class="request-row">
            <div>
              <b>{{ r.course_title || r.course }}</b>
              <p>
                {{ r.review_note || t("Waiting for instructor or administrator verification.") }}
              </p>
              <a v-if="r.receipt_name" :href="'/api/method/nightjar_learning.payments.receipt?request=' + encodeURIComponent(r.name)">{{ t("Download your receipt") }}</a>
            </div>
            <span class="status-pill">{{ t(r.status) }}</span>
          </div>
        </section></template
      >
      <div v-else class="empty">
        <p>{{ t("Sign in to see your saved progress.") }}</p>
        <a class="button" href="#view=login">{{ t("Sign in") }}</a>
      </div></template
    >
    <section v-else-if="view === 'payments'" class="page-intro">
      <h1>{{ t("Payment requests") }}</h1>
      <p v-if="staff">{{ t("Open your teaching workspace to review enrollment requests.") }}</p>
      <a v-if="staff" href="/lms/payment-requests" class="button">{{ t("Open payment requests") }}</a>
      <p v-else>{{ t("Check your enrollment requests in") }} <a href="#view=dashboard">{{ t("My learning") }}</a>.</p>
    </section>
    <template v-else-if="course"
      ><a
        class="back-link"
        :href="lesson ? `#course=${encodeURIComponent(course.name)}` : '#'"
        >{{ language === "ar" ? "→" : "←" }} {{ lesson ? course.title : t("All courses") }}</a
      ><template v-if="!route.lesson"
        ><section class="course-hero">
          <div>
            <div class="feature-facts">
              <span>{{ course.category }}</span
              ><span>{{ t(course.nj_difficulty || "Beginner") }}</span>
            </div>
            <h1>{{ course.title }}</h1>
            <p>{{ course.short_introduction }}</p>
            <div class="instructors">
              <span class="avatar">{{
                course.instructors[0]?.name?.[0] || "N"
              }}</span
              >{{ t("With") }} {{ course.instructors.map((i) => i.name).join(", ") }}
            </div>
          </div>
          <aside class="enrollment-card">
            <span class="big-play">▷</span><strong>{{ money(course) }}</strong>
            <p>{{ allLessons.length }} {{ t("lessons") }}. {{ t("Your own pace.") }}</p>
            <button
              v-if="course.can_learn"
              class="button"
              :disabled="!allLessons.length"
              @click="resume"
            >
              {{
                course.enrollment?.progress
                  ? t("Continue learning")
                  : t("Start learning")
              }}</button
            ><button v-else class="button" :disabled="busy" @click="enroll">
              {{
                course.paid_course ? t("Request enrollment") : t("Enroll for free")
              }}
            </button>
            <div v-if="course.enrollment" class="card-progress">
              <p>{{ Math.round(course.enrollment.progress || 0) }}% {{ t("complete") }}</p>
              <progress
                :value="course.enrollment.progress || 0"
                max="100"
                :aria-label="t('Course progress')"
              ></progress>
            </div>
            <small v-if="course.paid_course && !course.can_learn"
              >{{ t("Contact your administrator for payment instructions. Access opens after verification.") }}</small
            >
          </aside>
        </section>
        <div class="course-body">
          <section>
            <h2>{{ t("About this course") }}</h2>
            <div class="prose" v-html="safe(course.description)"></div>
          </section>
          <section>
            <h2>{{ t("Your learning path") }}</h2>
            <div
              v-for="(ch, i) in course.chapters"
              :key="ch.name"
              class="chapter"
            >
              <h3>
                <span>{{ String(i + 1).padStart(2, "0") }}</span
                >{{ ch.title }}
              </h3>
              <a
                v-for="(l, j) in ch.lessons"
                :key="l.name"
                class="outline-lesson"
                :href="
                  course.can_learn
                    ? `#course=${encodeURIComponent(course.name)}&lesson=${encodeURIComponent(l.name)}`
                    : undefined
                "
                :aria-disabled="!course.can_learn"
                ><span>{{ j + 1 }}</span
                ><b>{{ l.title }}</b
                ><small>{{ duration(l.duration) }}</small
                ><span>{{ course.can_learn ? "▷" : "⌑" }}</span></a
              >
            </div>
          </section>
        </div>
        <Reviews :key="course.name" :course="course.name"
      /></template>
      <template v-else-if="lesson"
        ><div class="lesson-heading">
          <div>
            <span class="intro-note">{{ course.title }}</span>
            <h1>{{ lesson.title }}</h1>
          </div>
          <span v-if="lesson.complete" class="complete-pill">✓ {{ t("Completed") }}</span>
        </div>
        <div class="learning-layout">
          <section class="lesson-main">
            <Player
              v-if="lesson.private_video"
              :key="lesson.name"
              :lesson="lesson.name"
            />
            <div v-else class="reading-banner">
              <span>✧</span>
              <div>
                <h2>{{ t("Take a moment to explore.") }}</h2>
                <p>{{ t("This lesson is ready to read below.") }}</p>
              </div>
            </div>
            <div class="lesson-actions">
              <span
                >{{ Math.round(course.enrollment?.progress || 0) }}% {{ t("of course complete") }}</span
              ><button
                class="button small"
                :disabled="busy || lesson.complete"
                @click="complete"
              >
                {{
                  lesson.complete ? `✓ ${t("Lesson completed")}` : t("Mark as complete")
                }}
              </button>
            </div>
            <iframe
              v-if="hasActivity"
              id="lesson-activity"
              class="activity-frame"
              :src="'/lms?nightjar_lesson=' + encodeURIComponent(lesson.name)"
              :style="{ height: activityHeight + 'px' }"
              :title="t('Lesson resources and activities')"
              allow="fullscreen; camera; microphone"
            />
            <article v-else class="prose lesson-content">
              <div v-if="lesson.body" v-html="markdown(lesson.body)"></div>
              <template v-for="(b, i) in blocks" :key="i"
                ><p
                  v-if="b.type === 'paragraph'"
                  v-html="safe(b.data.text)"
                ></p>
                <h3
                  v-else-if="b.type === 'header'"
                  v-html="safe(b.data.text)"
                ></h3>
                <pre
                  v-else-if="b.type === 'code'"
                ><code>{{b.data.code}}</code></pre>
                <div v-else class="native-block">
                  <p>
                    {{ t("This lesson includes an interactive activity or embedded resource.") }}
                  </p>
                </div></template
              >
            </article>
            <section class="discussion">
              <h2>
                {{ t("Lesson discussion") }} <span>{{ comments.length }}</span>
              </h2>
              <p class="muted">
                {{ t("Ask a question, share a discovery, or help someone move forward.") }}
              </p>
              <form @submit.prevent="sendComment">
                <div v-if="replyTo" class="replying">
                  {{ t("Replying to {name}", { name: replyTo.author }) }}
                  <button
                    type="button"
                    class="text-button"
                    @click="replyTo = null"
                  >
                    {{ t("Cancel") }}
                  </button>
                </div>
                <label class="sr-only" for="comment">{{ t("Your comment") }}</label
                ><textarea
                  id="comment"
                  v-model="commentText"
                  maxlength="4000"
                  required
                  :placeholder="t('What’s on your mind?')"
                ></textarea
                ><button
                  class="button small"
                  :disabled="busy || !commentText.trim()"
                >
                  {{
                    busy ? t("Posting…") : replyTo ? t("Post reply") : t("Post comment")
                  }}
                </button>
              </form>
              <div v-if="!comments.length" class="discussion-empty">
                {{ t("Be the first to start the conversation.") }}
              </div>
              <article
                v-for="c in comments"
                :key="c.name"
                class="comment"
                :class="{ reply: c.nj_reply_to }"
              >
                <span class="avatar">{{ c.author[0] }}</span>
                <div>
                  <div class="comment-author">
                    <b>{{ c.author }}</b
                    ><span v-if="c.instructor" class="instructor-tag"
                      >{{ t("Instructor") }}</span
                    ><time>{{
                      new Date(
                        c.creation.replace(" ", "T"),
                      ).toLocaleDateString()
                    }}</time>
                  </div>
                  <small v-if="c.nj_reply_to" class="muted"
                    >{{ t("In reply to") }}
                    {{
                      comments.find((x) => x.name === c.nj_reply_to)?.author ||
                      t("a comment")
                    }}</small
                  >
                  <div class="prose" v-html="safe(c.reply)"></div>
                  <button class="text-button" @click="replyTo = c">{{ t("Reply") }}</button
                  ><button
                    v-if="admin"
                    class="text-button danger"
                    :disabled="busy"
                    @click="removeComment(c)"
                  >
                    {{ t("Remove") }}
                  </button>
                </div>
              </article>
            </section>
          </section>
          <aside class="lesson-sidebar">
            <h2>{{ t("Your learning path") }}</h2>
            <progress
              :value="course.enrollment?.progress || 0"
              max="100"
              :aria-label="t('Course progress')"
            ></progress>
            <div v-for="(ch, i) in course.chapters" :key="ch.name">
              <h3>{{ i + 1 }}. {{ ch.title }}</h3>
              <a
                v-for="l in ch.lessons"
                :key="l.name"
                :href="`#course=${encodeURIComponent(course.name)}&lesson=${encodeURIComponent(l.name)}`"
                :class="{ selected: l.name === lesson.name }"
                ><span>{{ l.name === lesson.name ? "▶" : "▷" }}</span
                ><b>{{ l.title }}</b
                ><small>{{ duration(l.duration) }}</small></a
              >
            </div>
          </aside>
        </div></template
      ></template
    >
  </main>
  <footer class="site-footer" :inert="paymentOpen">
    <a class="brand" href="#">nightjar<span>learning</span></a>
    <p>{{ t("Stay curious. Keep building.") }}</p>
    <span>{{ t("Built for curious minds.") }}</span>
  </footer>
  <div
    v-if="paymentOpen"
    class="modal-backdrop"
    @click.self="closePayment"
  >
    <section
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="payment-title"
      @keydown.esc="closePayment"
      @keydown="trap"
    >
      <button
        class="modal-close quiet"
        :aria-label="t('Close payment request')"
        @click="closePayment" :disabled="busy"
      >
        ×</button
      ><span class="featured-label">{{ t("Your next step") }}</span>
      <h2 id="payment-title">{{ t("Request enrollment") }}</h2>
      <p>{{ course.title }} · {{ money(course) }}</p>
      <p>
        {{ t("Follow your administrator’s payment instructions, then enter the payment details below. You can also attach a receipt. Access opens after approval.") }}
      </p>
      <Notice :message="error" kind="error" @dismiss="error = ''" />
      <form @submit.prevent="sendPayment">
        <label for="payment-reference">{{ t("Payment details (required)") }}</label
        ><input
          id="payment-reference"
          v-model="paymentRef"
          :disabled="busy"
          minlength="3"
          maxlength="140"
          required
          :placeholder="t('For example: transfer reference, date, and payer name')"
        />
        <label for="payment-receipt">{{ t("Receipt (optional)") }}</label>
        <input id="payment-receipt" type="file" accept=".jpg,.jpeg,.png,.pdf" :disabled="busy" @change="chooseReceipt" aria-describedby="receipt-help" />
        <p id="receipt-help" class="muted">{{ t("One JPG, PNG, or PDF · up to 10 MB. Only you and authorized teaching staff can download it.") }}</p>
        <button class="button" :disabled="busy">
          {{ busy ? t("Sending…") : t("Send for verification") }}</button
        ><button type="button" class="quiet" @click="closePayment" :disabled="busy">
          {{ t("Cancel") }}
        </button>
      </form>
    </section>
  </div>
</template>
