<script setup>
import { ref, onMounted } from "vue";
import { rpc } from "./api";
const rows = ref([]),
  search = ref(""),
  page = ref(0),
  selected = ref(null),
  email = ref(""),
  name = ref(""),
  password = ref(""),
  confirm = ref(""),
  busy = ref(false),
  error = ref(""),
  notice = ref("");
async function load() {
  rows.value = await rpc("accounts.members", {
    search: search.value,
    start: page.value * 50,
  });
}
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
onMounted(() => run(load));
function select(row) {
  selected.value = row;
  password.value = "";
  confirm.value = "";
  notice.value = "";
}
function save() {
  run(async () => {
    const args = { password: password.value, confirm_password: confirm.value };
    if (selected.value?.name)
      await rpc(
        "accounts.set_student_password",
        { ...args, member: selected.value.name },
        true,
      );
    else
      await rpc(
        "accounts.add_student",
        { ...args, email: email.value, full_name: name.value },
        true,
      );
    selected.value = null;
    password.value = "";
    confirm.value = "";
    notice.value = "Account saved.";
    await load();
  });
}
</script>
<template>
  <section>
    <div class="section-heading">
      <div>
        <h1>Students</h1>
        <p>Create student accounts and set passwords without email setup.</p>
      </div>
      <button class="button" @click="select({})">Add student</button>
    </div>
    <p v-if="error" role="alert" class="notice error">{{ error }}</p>
    <p v-if="notice" role="status" class="notice success">{{ notice }}</p>
    <form
      class="filters"
      @submit.prevent="
        page = 0;
        run(load);
      "
    >
      <label class="search"
        ><input
          v-model="search"
          type="search"
          placeholder="Search by email"
          aria-label="Search students" /></label
      ><button class="button" :disabled="busy">Search</button>
    </form>
    <form
      v-if="selected"
      class="account-panel stack-form"
      @submit.prevent="save"
    >
      <h2>{{ selected.name ? "Set student password" : "New student" }}</h2>
      <p v-if="selected.name">{{ selected.name }}</p>
      <template v-else
        ><label
          >Full name<input v-model="name" required maxlength="140" /></label
        ><label
          >Email<input
            v-model="email"
            type="email"
            required /></label></template
      ><label
        >New password<input
          v-model="password"
          type="password"
          autocomplete="new-password"
          minlength="12"
          maxlength="128"
          required /></label
      ><label
        >Confirm password<input
          v-model="confirm"
          type="password"
          autocomplete="new-password"
          minlength="12"
          maxlength="128"
          required
      /></label>
      <div class="account-links">
        <button class="button" :disabled="busy">Save account</button
        ><button type="button" class="quiet" @click="selected = null">
          Cancel
        </button>
      </div>
    </form>
    <div v-for="r in rows" class="member-row" :key="r.name">
      <span class="avatar">{{ r.full_name?.[0] }}</span>
      <div>
        <b>{{ r.full_name }}</b>
        <p>{{ r.name }}</p>
      </div>
      <span>{{ r.enabled ? "Active" : "Disabled" }}</span
      ><button
        v-if="r.user_type === 'Website User'"
        class="quiet"
        @click="select(r)"
      >
        Set password</button
      ><a
        v-else
        class="text-button"
        :href="'/app/user/' + encodeURIComponent(r.name)"
        >Staff settings ↗</a
      >
    </div>
    <p v-if="!rows.length">No matching accounts.</p>
    <div class="account-links">
      <button
        class="quiet"
        :disabled="!page || busy"
        @click="
          page--;
          run(load);
        "
      >
        Previous</button
      ><span>Page {{ page + 1 }}</span
      ><button
        class="quiet"
        :disabled="rows.length < 50 || busy"
        @click="
          page++;
          run(load);
        "
      >
        Next</button
      ><a href="/app/user" class="text-button">Advanced user settings ↗</a>
    </div>
  </section>
</template>
