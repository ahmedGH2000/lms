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
const Player = defineAsyncComponent(() => import("./Player.vue"));
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
  adminNotes = ref({});
const signedIn = boot.user !== "Guest",
  admin =
    boot.user === "Administrator" || boot.roles.includes("System Manager"),
  staff =
    admin ||
    boot.roles.some((x) => ["Course Creator", "Moderator"].includes(x));
const view = computed(
    () => route.value.view || (route.value.course ? "course" : "catalog"),
  ),
  firstName = computed(() => boot.full_name?.split(" ")[0] || "Learner");
const featured = computed(
    () => courses.value.find((c) => c.featured) || courses.value[0],
  ),
  allLessons = computed(
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
const nativeUrl = computed(() => {
  let ch = 1,
    l = 1;
  course.value?.chapters.forEach((c, i) =>
    c.lessons.forEach((x, j) => {
      if (x.name === lesson.value?.name) {
        ch = i + 1;
        l = j + 1;
      }
    }),
  );
  return `/lms/courses/${encodeURIComponent(course.value?.name || "")}/learn/${ch}-${l}`;
});
function documentFocus() {
  document.getElementById("main")?.focus();
}
let timer,
  seq = 0,
  routeSeq = 0,
  previousFocus;
async function catalog() {
  const n = ++seq;
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
  } catch (e) {
    error.value = e.message;
  }
}
async function load() {
  const n = ++routeSeq;
  route.value = Object.fromEntries(new URLSearchParams(location.hash.slice(1)));
  mobile.value = false;
  window.scrollTo({top:0,behavior:"instant"});
  error.value = "";
  notice.value = "";
  loading.value = true;
  lesson.value = null;
  course.value = null;
  paymentOpen.value = false;
  replyTo.value = null;
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
          throw new Error("This lesson belongs to another course.");
        lesson.value = l;
        comments.value = await rpc("api.discussion", { lesson: l.name });
      }
    } else if (view.value === "dashboard" && signedIn) {
      mine.value = await rpc("api.dashboard");
      requests.value = await rpc("payments.requests");
    } else if (view.value === "payments" && admin)
      requests.value = await rpc("payments.requests");
    else if (view.value === "catalog") await catalog();
  } catch (e) {
    if (n === routeSeq) error.value = e.message;
  } finally {
    if (n === routeSeq) loading.value = false;
  }
}
async function act(fn) {
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
    location.href = "/login?redirect-to=%2Flearn";
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
function sendPayment() {
  act(async () => {
    await rpc(
      "payments.request_payment",
      { course: course.value.name, reference: paymentRef.value },
      true,
    );
    paymentOpen.value = false;
    notice.value =
      "Preview request added. No payment or enrollment request has been sent.";
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
      ? "Lesson completed in this preview. Changes reset when you reopen the file."
      : "Complete the required assessments in Frappe Learning first.";
  });
}
function decide(r, decision) {
  act(async () => {
    await rpc(
      "payments.decide",
      { request: r.name, decision, note: adminNotes.value[r.name] || "" },
      true,
    );
    requests.value = await rpc("payments.requests");
    notice.value = `Request ${decision.toLowerCase()}.`;
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
  if (open) {
    previousFocus = document.activeElement;
    await nextTick();
    document.getElementById("payment-reference")?.focus();
  } else previousFocus?.focus?.();
});
watch([search, category, level], () => {
  page.value = 0;
  clearTimeout(timer);
  timer = setTimeout(catalog, 250);
});
watch(page, catalog);
onMounted(() => {
  window.addEventListener("hashchange", load);
  load();
});
onBeforeUnmount(() => {
  clearTimeout(timer);
  window.removeEventListener("hashchange", load);
});
</script>
<template>
  <a class="skip-link" href="#main" @click.prevent="documentFocus"
    >Skip to content</a
  >
  <header class="site-header">
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
        aria-label="Toggle navigation"
      >
        ☰
      </button>
      <nav :class="{ open: mobile }" aria-label="Main navigation">
        <a href="#" :class="{ active: view === 'catalog' }">Explore courses</a
        ><a href="#view=dashboard" :class="{ active: view === 'dashboard' }"
          >My learning</a
        ><a v-if="staff" href="/lms">Teaching studio ↗</a
        ><a v-if="admin" href="#view=payments">Payments</a>
      </nav>
      <a
        v-if="!signedIn"
        class="button small"
        href="/login?redirect-to=%2Flearn"
        >Sign in</a
      ><a
        v-else
        class="account"
        href="/me"
        :aria-label="'Manage account for ' + boot.full_name"
        ><span>{{ firstName[0] }}</span
        ><b>{{ firstName }}</b></a
      >
    </div>
  </header>
  <main id="main" class="main-shell" tabindex="-1">
    <div v-if="error" class="notice error" role="alert">
      {{ error }} <button class="text-button" @click="load">Try again</button>
    </div>
    <div v-if="notice" class="notice success" role="status">{{ notice }}</div>
    <div v-if="loading" class="loading" role="status">
      <i></i>Opening your learning space…
    </div>
    <template v-else-if="view === 'catalog'"
      ><section class="catalog-intro">
        <div>
          <div class="intro-note"><i></i>Small lessons. Lasting skills.</div>
          <h1>Make room for<br />your next breakthrough.</h1>
          <p>
            Go from understanding the idea to building it yourself.<br
              class="desktop-only"
            />
            Find your next course and keep moving forward.
          </p>
        </div>
        <div class="intro-side">
          <svg viewBox="0 0 120 100" aria-hidden="true">
            <path
              d="M18 70 59 15 101 70 59 92ZM18 70 59 47 101 70M59 15v77"
            /></svg
          ><span>Learn at your pace.<br />Build with confidence.</span>
        </div>
      </section>
      <section
        v-if="featured && !search && !category && !level && !page"
        class="featured"
      >
        <div class="featured-art">
          <div class="code-window">
            <div class="window-dots">
              <i></i><i></i><i></i><span>your-next-project</span>
            </div>
            <pre><span class="code-muted">// Every great project begins here.</span>
<span class="code-purple">const</span> nextStep = {
  curiosity: <span class="code-blue">true</span>,
  practice: <span class="code-green">'a little, every day'</span>,
  possibilities: <span class="code-blue">Infinity</span>
};

<span class="code-purple">await</span> you.build(nextStep);▌</pre>
            <div class="terminal-line">✓ &nbsp; Ready when you are.</div>
          </div>
          <span class="art-sticker">Press play.<br />Make progress.</span>
        </div>
        <div class="featured-copy">
          <span class="featured-label">In focus</span>
          <h2>{{ featured.title }}</h2>
          <p>{{ featured.short_introduction }}</p>
          <div class="feature-facts">
            <span>{{ featured.nj_difficulty || "Beginner" }}</span
            ><span>{{ featured.lessons }} lessons</span
            ><span>{{ money(featured) }}</span>
          </div>
          <a
            class="button"
            :href="`#course=${encodeURIComponent(featured.name)}`"
            >Explore this course ↗</a
          >
        </div>
      </section>
      <section class="catalog-section">
        <div class="section-heading">
          <div>
            <h2>Find your next skill</h2>
            <p>A little curiosity can take you a long way.</p>
          </div>
          <span class="count">{{ total }} courses</span>
        </div>
        <div class="filters">
          <label class="search-field"
            ><span aria-hidden="true">⌕</span
            ><input
              v-model="search"
              type="search"
              placeholder="What do you want to learn?"
              aria-label="Search courses" /></label
          ><label
            ><span class="sr-only">Category</span
            ><select v-model="category">
              <option value="">All topics</option>
              <option v-for="c in categories" :key="c">{{ c }}</option>
            </select></label
          ><label
            ><span class="sr-only">Difficulty</span
            ><select v-model="level">
              <option value="">All levels</option>
              <option>Beginner</option>
              <option>Intermediate</option>
              <option>Advanced</option>
            </select></label
          >
        </div>
        <div class="course-grid">
          <CourseCard
            v-for="(c, i) in courses"
            :key="c.name"
            :course="c"
            :index="i"
          />
        </div>
        <div v-if="!courses.length" class="empty">
          <h3>
            {{
              search || category || level
                ? "No matching courses."
                : "Your learning library starts here."
            }}
          </h3>
          <p>
            {{
              search || category || level
                ? "Try another topic or clear your filters."
                : "Publish your first course in the teaching studio."
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
            Clear filters</button
          ><a v-else-if="staff" class="button" href="/lms"
            >Open teaching studio</a
          >
        </div>
        <div v-if="total > 24" class="pagination">
          <button class="quiet" :disabled="!page" @click="page--">
            Previous</button
          ><span>Page {{ page + 1 }}</span
          ><button
            class="quiet"
            :disabled="(page + 1) * 24 >= total"
            @click="page++"
          >
            Next
          </button>
        </div>
      </section>
      <aside v-if="!signedIn" class="join-strip">
        <div>
          <h2>Your next chapter starts with one lesson.</h2>
          <p>Create an account to save progress and join the conversation.</p>
        </div>
        <a class="button" href="/login#signup">Create an account</a>
      </aside></template
    >
    <template v-else-if="view === 'dashboard'"
      ><section class="page-intro">
        <span class="intro-note">Your learning space</span>
        <h1>
          {{
            signedIn
              ? `Keep going, ${firstName}.`
              : "A place for your progress."
          }}
        </h1>
        <p>Pick up where you left off. Every lesson brings you closer.</p>
      </section>
      <template v-if="signedIn"
        ><div class="stats">
          <div>
            <strong>{{ mine.length }}</strong
            ><span>Enrolled courses</span>
          </div>
          <div>
            <strong>{{ mine.filter((c) => c.progress >= 100).length }}</strong
            ><span>Courses completed</span>
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
            ><span>Average course progress</span>
          </div>
        </div>
        <div class="section-heading">
          <h2>Continue learning</h2>
          <a class="text-button" href="#">Explore more courses ↗</a>
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
          <h3>Find something you’re curious about.</h3>
          <p>Your enrolled courses will appear here.</p>
          <a class="button" href="#">Explore courses</a>
        </div>
        <section v-if="requests.length" class="request-section">
          <h2>Payment requests</h2>
          <div v-for="r in requests" :key="r.name" class="request-row">
            <div>
              <b>{{ r.course }}</b>
              <p>
                {{ r.review_note || "Waiting for administrator verification." }}
              </p>
            </div>
            <span class="status-pill">{{ r.status }}</span>
          </div>
        </section></template
      >
      <div v-else class="empty">
        <p>Sign in to see your saved progress.</p>
        <a class="button" href="/login?redirect-to=%2Flearn">Sign in</a>
      </div></template
    >
    <template v-else-if="view === 'payments'"
      ><section class="page-intro">
        <h1>Payment approvals</h1>
        <p>Verify each transfer independently before granting access.</p>
      </section>
      <div v-if="!admin" class="empty">
        Only a system administrator can review payments.
      </div>
      <template v-else
        ><div v-if="!requests.length" class="empty">
          No payment requests to review.
        </div>
        <div v-for="r in requests" :key="r.name" class="approval-card">
          <div>
            <h3>{{ r.course }}</h3>
            <p>{{ r.member }}</p>
            <p>
              Reference: {{ r.reference }} · {{ r.currency }} {{ r.amount }}
            </p>
            <span class="status-pill">{{ r.status }}</span>
          </div>
          <div
            v-if="['Pending', 'Approved'].includes(r.status)"
            class="approval-actions"
          >
            <label :for="r.name">Verification note</label
            ><textarea
              :id="r.name"
              v-model="adminNotes[r.name]"
              maxlength="1000"
              placeholder="Record how you verified the payment"
            ></textarea>
            <div>
              <button
                v-if="r.status === 'Pending'"
                class="button"
                :disabled="busy"
                @click="decide(r, 'Approved')"
              >
                Approve access</button
              ><button
                v-if="r.status === 'Pending'"
                class="quiet"
                :disabled="busy"
                @click="decide(r, 'Rejected')"
              >
                Reject</button
              ><button
                v-else
                class="quiet"
                :disabled="busy"
                @click="decide(r, 'Revoked')"
              >
                Revoke access
              </button>
            </div>
          </div>
        </div></template
      ></template
    >
    <template v-else-if="course"
      ><a
        class="back-link"
        :href="lesson ? `#course=${encodeURIComponent(course.name)}` : '#'"
        >← {{ lesson ? course.title : "All courses" }}</a
      ><template v-if="!route.lesson"
        ><section class="course-hero">
          <div>
            <div class="feature-facts">
              <span>{{ course.category }}</span
              ><span>{{ course.nj_difficulty || "Beginner" }}</span>
            </div>
            <h1>{{ course.title }}</h1>
            <p>{{ course.short_introduction }}</p>
            <div class="instructors">
              <span class="avatar">{{
                course.instructors[0]?.name?.[0] || "N"
              }}</span
              >With {{ course.instructors.map((i) => i.name).join(", ") }}
            </div>
          </div>
          <aside class="enrollment-card">
            <span class="big-play">▷</span><strong>{{ money(course) }}</strong>
            <p>{{ allLessons.length }} lessons. Your own pace.</p>
            <button
              v-if="course.can_learn"
              class="button"
              :disabled="!allLessons.length"
              @click="resume"
            >
              {{
                course.enrollment?.progress
                  ? "Continue learning"
                  : "Start learning"
              }}</button
            ><button v-else class="button" :disabled="busy" @click="enroll">
              {{
                course.paid_course ? "Request enrollment" : "Enroll for free"
              }}
            </button>
            <div v-if="course.enrollment" class="card-progress">
              <p>{{ Math.round(course.enrollment.progress || 0) }}% complete</p>
              <progress
                :value="course.enrollment.progress || 0"
                max="100"
                aria-label="Course progress"
              ></progress>
            </div>
            <small v-if="course.paid_course && !course.can_learn"
              >Contact your administrator for payment instructions. Access opens
              after verification.</small
            >
          </aside>
        </section>
        <div class="course-body">
          <section>
            <h2>About this course</h2>
            <div class="prose" v-html="safe(course.description)"></div>
          </section>
          <section>
            <h2>Your learning path</h2>
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
        </div></template
      >
      <template v-else-if="lesson"
        ><div class="lesson-heading">
          <div>
            <span class="intro-note">{{ course.title }}</span>
            <h1>{{ lesson.title }}</h1>
          </div>
          <span v-if="lesson.complete" class="complete-pill">✓ Completed</span>
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
                <h2>Take a moment to explore.</h2>
                <p>This lesson is ready to read below.</p>
              </div>
            </div>
            <div class="lesson-actions">
              <span
                >{{ Math.round(course.enrollment?.progress || 0) }}% of course
                complete</span
              ><button
                class="button small"
                :disabled="busy || lesson.complete"
                @click="complete"
              >
                {{
                  lesson.complete ? "✓ Lesson completed" : "Mark as complete"
                }}
              </button>
            </div>
            <article class="prose lesson-content">
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
                    This lesson includes an interactive activity or embedded
                    resource.
                  </p>
                  <a class="text-button" :href="nativeUrl"
                    >Open in Frappe Learning ↗</a
                  >
                </div></template
              >
            </article>
            <section class="discussion">
              <h2>
                Lesson discussion <span>{{ comments.length }}</span>
              </h2>
              <p class="muted">
                Ask a question, share a discovery, or help someone move forward.
              </p>
              <form @submit.prevent="sendComment">
                <div v-if="replyTo" class="replying">
                  Replying to {{ replyTo.author }}
                  <button
                    type="button"
                    class="text-button"
                    @click="replyTo = null"
                  >
                    Cancel
                  </button>
                </div>
                <label class="sr-only" for="comment">Your comment</label
                ><textarea
                  id="comment"
                  v-model="commentText"
                  maxlength="4000"
                  required
                  placeholder="What’s on your mind?"
                ></textarea
                ><button
                  class="button small"
                  :disabled="busy || !commentText.trim()"
                >
                  Post {{ replyTo ? "reply" : "comment" }}
                </button>
              </form>
              <div v-if="!comments.length" class="discussion-empty">
                Be the first to start the conversation.
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
                      >Instructor</span
                    ><time>{{
                      new Date(
                        c.creation.replace(" ", "T"),
                      ).toLocaleDateString()
                    }}</time>
                  </div>
                  <small v-if="c.nj_reply_to" class="muted"
                    >In reply to
                    {{
                      comments.find((x) => x.name === c.nj_reply_to)?.author ||
                      "a comment"
                    }}</small
                  >
                  <div class="prose" v-html="safe(c.reply)"></div>
                  <button class="text-button" @click="replyTo = c">
                    Reply
                  </button>
                </div>
              </article>
            </section>
          </section>
          <aside class="lesson-sidebar">
            <h2>Course contents</h2>
            <progress
              :value="course.enrollment?.progress || 0"
              max="100"
              aria-label="Course progress"
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
            <a class="native-link" :href="nativeUrl"
              >Quizzes & other resources ↗</a
            >
          </aside>
        </div></template
      ></template
    >
  </main>
  <footer class="site-footer">
    <a class="brand" href="#">nightjar<span>learning</span></a>
    <p>Stay curious. Keep building.</p>
    <a href="/lms">Powered by Frappe Learning ↗</a>
  </footer>
  <div
    v-if="paymentOpen"
    class="modal-backdrop"
    @click.self="paymentOpen = false"
  >
    <section
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="payment-title"
      @keydown.esc="paymentOpen = false"
      @keydown="trap"
    >
      <button
        class="modal-close quiet"
        aria-label="Close payment request"
        @click="paymentOpen = false"
      >
        ×</button
      ><span class="featured-label">Your next step</span>
      <h2 id="payment-title">Request enrollment</h2>
      <p>{{ course.title }} · {{ money(course) }}</p>
      <p>
        Follow your administrator’s payment instructions, then enter the
        transfer reference. A reference alone does not confirm payment.
      </p>
      <p v-if="error" class="notice error" role="alert">{{ error }}</p>
      <form @submit.prevent="sendPayment">
        <label for="payment-reference">Transfer or receipt reference</label
        ><input
          id="payment-reference"
          v-model="paymentRef"
          minlength="3"
          maxlength="140"
          required
          placeholder="Your payment reference"
        /><button class="button" :disabled="busy">Send for verification</button
        ><button type="button" class="quiet" @click="paymentOpen = false">
          Cancel
        </button>
      </form>
    </section>
  </div>
</template>
