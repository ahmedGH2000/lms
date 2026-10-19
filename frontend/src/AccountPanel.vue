<script setup>
import { ref, onMounted } from "vue";
import Notice from "./Notice.vue";
import { rpc, boot } from "./api";
const props = defineProps({ mode: String });
const email = ref(""),
  name = ref(""),
  last = ref(""),
  bio = ref(""),
  password = ref(""),
  confirm = ref(""),
  old = ref("");
const profileLoading = ref(props.mode === "profile" && boot.user !== "Guest");
const busy = ref(false),
  error = ref(""),
  message = ref("");
const otp = ref(""),
  challenge = ref(null);
const authenticated = boot.user !== "Guest";
onMounted(async () => {
  if (props.mode === "login" && sessionStorage.getItem("nightjar-registered")) {
    email.value = sessionStorage.getItem("nightjar-registered");
    sessionStorage.removeItem("nightjar-registered");
    message.value = "Your account is ready. Sign in with your email and password.";
  }
  if (sessionStorage.getItem("nightjar-password-updated")) {
    message.value = "Password changed. Other sessions have been signed out.";
    sessionStorage.removeItem("nightjar-password-updated");
  }
  if (props.mode === "profile" && authenticated) {
    try {
      const p = await rpc("accounts.profile");
      email.value = p.email;
      name.value = p.first_name;
      last.value = p.last_name || "";
      bio.value = p.bio || "";
    } catch (e) {
      error.value = e.message;
    } finally {
      profileLoading.value = false;
    }
  }
});
async function submit(action = props.mode) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  message.value = "";
  try {
    if (action === "signup") {
      await rpc(
        "accounts.register",
        {
          email: email.value,
          full_name: name.value,
          password: password.value,
          confirm_password: confirm.value,
        },
        true,
      );
      password.value = "";
      confirm.value = "";
      sessionStorage.setItem("nightjar-registered", email.value);
      location.hash = "view=login";
    } else if (action === "login") {
      const d = await rpc(
        "accounts.login",
        {
          email: email.value,
          password: password.value,
          otp: otp.value,
          tmp_id: challenge.value?.tmp_id,
        },
        true,
      );
      if (d.signed_in) {
        if (d.landing_page === "/lms") location.assign("/lms");
        else { location.hash = "view=dashboard"; location.reload(); }
      } else if (d.verification) {
        challenge.value = d;
        message.value =
          d.verification.prompt || "Enter your verification code.";
      } else if (d.redirect_to) {
        const key = new URL(d.redirect_to, location.origin).searchParams.get(
          "key",
        );
        if (key) location.hash = "view=reset&key=" + encodeURIComponent(key);
        else
          throw new Error(
            "Your password must be reset. Contact your administrator.",
          );
      } else throw new Error("Sign-in could not be completed.");
    } else if (action === "forgot") {
      message.value = await rpc(
        "accounts.recover",
        { email: email.value },
        true,
      );
    } else if (action === "profile") {
      await rpc(
        "accounts.save_profile",
        { first_name: name.value, last_name: last.value, bio: bio.value },
        true,
      );
      message.value = "Profile saved.";
    } else if (action === "password" || action === "reset") {
      await rpc(
        "accounts.change_password",
        {
          password: password.value,
          confirm_password: confirm.value,
          old_password: old.value,
          key:
            action === "reset"
              ? new URLSearchParams(location.hash.slice(1)).get("key")
              : null,
        },
        true,
      );
      password.value = "";
      confirm.value = "";
      old.value = "";
      sessionStorage.setItem("nightjar-password-updated", "1");
      location.hash = "view=profile";
      location.reload();
    } else if (action === "logout") {
      await rpc("accounts.logout", {}, true);
      location.href = "/learn";
    }
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <section class="account-layout">
    <div class="account-story">
      <span class="intro-note">Your learning space</span>
      <h1>
        {{
          mode === "profile"
            ? "Make it yours."
            : "A little practice. A lot of possibility."
        }}
      </h1>
      <p>Your courses, conversations, and progress. All in one place.</p>
      <div class="account-art" aria-hidden="true">
        <span>{ learn }</span><span>build · repeat</span>
      </div>
    </div>
    <div class="account-panel">
      <h2>
        {{
          {
            signup: "Create your account",
            login: "Welcome back",
            forgot: "Recover your account",
            reset: "Choose a new password",
            profile: "Account settings",
          }[mode]
        }}
      </h2>
      <Notice :message="error" kind="error" @dismiss="error = ''" />
      <Notice :message="message" @dismiss="message = ''" />
      <template v-if="mode === 'profile' && !authenticated"
        ><p>Sign in to manage your account.</p>
        <a class="button" href="#view=login">Sign in</a></template
      >
      <p v-else-if="profileLoading" role="status">Loading your account…</p>
      <template v-else>
        <form
          v-if="mode !== 'reset'"
          class="stack-form"
          @submit.prevent="submit()"
        >
          <label v-if="['signup', 'profile'].includes(mode)"
            >{{ mode === "profile" ? "First name" : "Full name"
            }}<input
              v-model="name"
              autocomplete="given-name"
              maxlength="140"
              required
          /></label>
          <label v-if="mode === 'profile'"
            >Last name<input
              v-model="last"
              autocomplete="family-name"
              maxlength="140"
          /></label>
          <label
            >Email address<input
              v-model="email"
              :type="mode === 'login' ? 'text' : 'email'"
              autocomplete="email"
              :disabled="mode === 'profile'"
              required
          /></label>
          <label v-if="['signup', 'login'].includes(mode)"
            >Password<input
              v-model="password"
              type="password"
              :autocomplete="
                mode === 'signup' ? 'new-password' : 'current-password'
              "
              :minlength="mode === 'signup' ? 12 : undefined"
              maxlength="128"
              required
          /></label>
          <label v-if="challenge"
            >Verification code<input
              v-model="otp"
              autocomplete="one-time-code"
              required
          /></label>
          <label v-if="mode === 'signup'"
            >Confirm password<input
              v-model="confirm"
              type="password"
              autocomplete="new-password"
              minlength="12"
              maxlength="128"
              required
          /></label>
          <p v-if="mode === 'signup'" class="muted">
            Use at least 12 characters. Your email is used for account recovery.
          </p>
          <label v-if="mode === 'profile'"
            >About you<textarea v-model="bio" maxlength="2000"></textarea>
          </label>
          <button class="button" :disabled="busy">
            {{
              busy
                ? "Please wait…"
                : {
                    signup: "Create account",
                    login: "Sign in",
                    forgot: "Request reset email",
                    profile: "Save profile",
                  }[mode]
            }}
          </button>
        </form>
        <form
          v-if="['profile', 'reset'].includes(mode)"
          class="stack-form password-form"
          @submit.prevent="submit(mode === 'reset' ? 'reset' : 'password')"
        >
          <h3>Change password</h3>
          <label v-if="mode === 'profile'"
            >Current password<input
              v-model="old"
              type="password"
              autocomplete="current-password"
              required
          /></label>
          <label
            >New password<input
              v-model="password"
              type="password"
              autocomplete="new-password"
              minlength="12"
              maxlength="128"
              required
          /></label>
          <label
            >Confirm new password<input
              v-model="confirm"
              type="password"
              autocomplete="new-password"
              minlength="12"
              maxlength="128"
              required
          /></label>
          <button class="button" :disabled="busy">Save password</button>
        </form>
        <div class="account-links">
          <a v-if="mode !== 'login' && mode !== 'profile'" href="#view=login"
            >Already registered? Sign in</a
          ><template v-if="mode === 'login'"
            ><a href="#view=signup">Create an account</a
            ><a href="#view=forgot">Forgot password?</a></template
          ><button
            v-if="mode === 'profile'"
            class="quiet"
            :disabled="busy"
            @click="submit('logout')"
          >
            Sign out
          </button>
        </div>
      </template>
    </div>
  </section>
</template>
