<script setup>
import { ref, onMounted } from "vue";
import Notice from "./Notice.vue";
import PasswordField from "./PasswordField.vue";
import { rpc, boot } from "./api";
import { t } from "./i18n";
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
    message.value = t("Your account is ready. Sign in with your email and password.");
  }
  if (sessionStorage.getItem("nightjar-password-updated")) {
    message.value = t("Password changed. Other sessions have been signed out.");
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
          d.verification.prompt || t("Enter your verification code.");
      } else if (d.redirect_to) {
        const key = new URL(d.redirect_to, location.origin).searchParams.get(
          "key",
        );
        if (key) location.hash = "view=reset&key=" + encodeURIComponent(key);
        else
          throw new Error(
            t("Your password must be reset. Contact your administrator."),
          );
      } else throw new Error(t("Sign-in could not be completed."));
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
      message.value = t("Profile saved.");
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
    error.value = t(e.message);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <section class="account-layout">
    <div class="account-story">
      <span class="intro-note">{{ t("Your learning space") }}</span>
      <h1>
        {{
          mode === "profile"
            ? t("Make it yours.")
            : t("A little practice. A lot of possibility.")
        }}
      </h1>
      <p>{{ t("Your courses, conversations, and progress. All in one place.") }}</p>
      <ol class="study-path">
        <li><span aria-hidden="true">1</span>{{ t("Choose a course") }}</li>
        <li><span aria-hidden="true">2</span>{{ t("Learn at your own pace") }}</li>
        <li><span aria-hidden="true">3</span>{{ t("Pick up where you left off") }}</li>
      </ol>
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
            ? t({
                signup: "Create your account",
                login: "Welcome back",
                forgot: "Recover your account",
                reset: "Choose a new password",
                profile: "Account settings",
              }[mode])
            : ""
        }}
      </h2>
      <Notice :message="error" kind="error" @dismiss="error = ''" />
      <Notice :message="message" @dismiss="message = ''" />
      <template v-if="mode === 'profile' && !authenticated"
        ><p>{{ t("Sign in to manage your account.") }}</p>
        <a class="button" href="#view=login">{{ t("Sign in") }}</a></template
      >
      <p v-else-if="profileLoading" role="status">{{ t("Loading your account…") }}</p>
      <template v-else>
        <form
          v-if="mode !== 'reset'"
          class="stack-form"
          @submit.prevent="submit()"
        >
          <label v-if="['signup', 'profile'].includes(mode)"
            >{{ mode === "profile" ? t("First name") : t("Full name")
            }}<input
              v-model="name"
              autocomplete="given-name"
              maxlength="140"
              required
          /></label>
          <label v-if="mode === 'profile'"
            >{{ t("Last name") }}<input
              v-model="last"
              autocomplete="family-name"
              maxlength="140"
          /></label>
          <label
            >{{ t("Email address") }}<input
              v-model="email"
              :type="mode === 'login' ? 'text' : 'email'"
              autocomplete="email"
              :disabled="mode === 'profile'"
              required
          /></label>
          <PasswordField v-if="['signup', 'login'].includes(mode)"
            v-model="password" :label="t('Password')" :new-password="mode === 'signup'" />
          <a v-if="mode === 'login'" class="password-recovery" href="#view=forgot">{{ t("Forgot password?") }}</a>
          <label v-if="challenge"
            >{{ t("Verification code") }}<input
              v-model="otp"
              autocomplete="one-time-code"
              required
          /></label>
          <PasswordField v-if="mode === 'signup'" v-model="confirm"
            :label="t('Confirm password')" :confirm-with="password" />
          <p v-if="mode === 'signup'" class="muted">
            {{ t("Your email is used for account recovery.") }}
          </p>
          <label v-if="mode === 'profile'"
            >{{ t("About you") }}<textarea v-model="bio" maxlength="2000"></textarea>
          </label>
          <button class="button" :disabled="busy">
            {{
              busy
                ? t("Please wait…")
                : t({
                    signup: "Create account",
                    login: "Sign in",
                    forgot: "Request reset email",
                    profile: "Save profile",
                  }[mode])
            }}
          </button>
        </form>
        <form
          v-if="['profile', 'reset'].includes(mode)"
          class="stack-form password-form"
          @submit.prevent="submit(mode === 'reset' ? 'reset' : 'password')"
        >
          <h3>{{ t("Change password") }}</h3>
          <PasswordField v-if="mode === 'profile'" v-model="old" :label="t('Current password')" />
          <PasswordField v-model="password" :label="t('New password')" new-password />
          <PasswordField v-model="confirm" :label="t('Confirm new password')" :confirm-with="password" />
          <button class="button" :disabled="busy">{{ t("Save password") }}</button>
        </form>
        <div class="account-links">
          <a v-if="mode !== 'login' && mode !== 'profile'" href="#view=login"
            >{{ t("Already registered? Sign in") }}</a
          ><template v-if="mode === 'login'"
            ><a href="#view=signup">{{ t("Create an account") }}</a
            ></template
          ><button
            v-if="mode === 'profile'"
            class="quiet"
            :disabled="busy"
            @click="submit('logout')"
          >
            {{ t("Sign out") }}
          </button>
        </div>
      </template>
    </div>
  </section>
</template>

<style scoped>
.account-panel { border-radius: 18px; border-top: 3px solid #58b9ec; box-shadow: 0 24px 80px #0003; padding: 36px; }
.account-panel h2 { font-size: 30px; margin-bottom: 26px; }
.stack-form > .button { justify-self: stretch; min-height: 50px; margin-top: 4px; }
.password-recovery { color: #b1deff; justify-self: end; font-size: 14px; padding-block: 8px; margin-top: -10px; }
.password-recovery:hover { text-decoration: underline; }
.account-links { border-top: 1px solid var(--line); padding-top: 22px; }
.study-path { list-style: none; padding: 0; margin: 40px 0 0; max-width: 420px; }
.study-path li { display: flex; align-items: center; gap: 16px; min-height: 68px; color: #c4d9e9; position: relative; }
.study-path li + li::before { content: ""; position: absolute; inset-inline-start: 19px; top: -14px; height: 28px; border-inline-start: 1px solid #436079; }
.study-path li > span { width: 40px; height: 40px; display: grid; place-items: center; border: 1px solid #436079; border-radius: 12px; color: #87d5ec; font-size: 14px; }
@media (max-width: 760px) {
  .account-panel { padding: 24px 20px; }
  .study-path { display: none; }
  .account-story h1 { font-size: 34px; }
  .account-story p { font-size: 16px; }
}
</style>
