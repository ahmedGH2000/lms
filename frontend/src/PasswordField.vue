<script setup>
import { computed, shallowRef, useId, useTemplateRef, watch, watchEffect } from "vue";
import { t } from "./i18n";

const props = defineProps({
  label: { type: String, required: true },
  newPassword: Boolean,
  confirmWith: { type: String, default: undefined },
  disabled: Boolean,
});
const model = defineModel({ type: String, required: true });
const id = `password-${useId()}`;
const input = useTemplateRef("input");
const visible = shallowRef(false);
const touched = shallowRef(false);
const capsLock = shallowRef(false);
const rules = computed(() => [
  { label: t("8–128 characters"), met: [...model.value].length >= 8 && [...model.value].length <= 128 },
  { label: t("An uppercase letter (A–Z)"), met: /[A-Z]/.test(model.value) },
  { label: t("A special character (e.g. ! @ #)"), met: /[\p{P}\p{S}]/u.test(model.value) },
]);
const validation = computed(() => {
  if (!model.value) return "";
  if (props.newPassword && rules.value.some((rule) => !rule.met))
    return t("Use 8–128 characters, an uppercase letter, and a special character.");
  if (props.confirmWith !== undefined && model.value !== props.confirmWith)
    return t("The passwords do not match.");
  return "";
});
watchEffect(() => input.value?.setCustomValidity(validation.value));
watch(model, (value) => {
  if (!value) { visible.value = false; touched.value = false; }
});
function checkCaps(event) { capsLock.value = event.getModifierState?.("CapsLock") || false; }
</script>

<template>
  <div class="password-field">
    <label :for="id" class="password-label">{{ label }}</label>
    <div class="password-control" :class="{ 'has-error': touched && validation }">
      <input
        :id="id" ref="input" v-model="model" :type="visible ? 'text' : 'password'"
        :autocomplete="newPassword || confirmWith !== undefined ? 'new-password' : 'current-password'"
        :disabled="disabled" :aria-describedby="`${id}-help`"
        :aria-invalid="touched && validation ? 'true' : undefined"
        autocapitalize="off" :spellcheck="false" required dir="ltr"
        @blur="touched = true; capsLock = false" @invalid="touched = true"
        @keydown="checkCaps" @keyup="checkCaps"
      />
      <button type="button" class="password-toggle" :disabled="disabled"
        :aria-controls="id" :aria-label="t(visible ? 'Hide {field}' : 'Show {field}', { field: label })"
        @click="visible = !visible">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
          <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
          <circle cx="12" cy="12" r="3" />
          <path v-if="visible" d="m3 3 18 18" />
        </svg>
        <span>{{ t(visible ? "Hide" : "Show") }}</span>
      </button>
    </div>
    <div :id="`${id}-help`" class="password-help">
      <ul v-if="newPassword" class="password-rules" :aria-label="t('Password requirements')">
        <li v-for="rule in rules" :key="rule.label" :class="{ met: rule.met }">
          <span aria-hidden="true">{{ rule.met ? "✓" : "–" }}</span>
          <span class="sr-only">{{ t(rule.met ? 'Met:' : 'Needed:') }} </span>{{ rule.label }}
        </li>
      </ul>
      <p v-if="touched && validation" class="password-error" role="status">{{ validation }}</p>
      <p v-else-if="confirmWith !== undefined && model && !validation" class="password-match">✓ {{ t("Passwords match") }}</p>
      <p v-if="capsLock" class="password-caps" role="status">{{ t("Caps Lock is on") }}</p>
    </div>
  </div>
</template>

<style scoped>
.password-field { display: grid; gap: 8px; min-width: 0; }
.password-label { font-size: 15px; font-weight: 600; }
.password-control { display: flex; align-items: center; background: #07111f; border: 1px solid #4a607a; border-radius: 9px; }
.password-control:focus-within { border-color: #7ccaff; box-shadow: 0 0 0 3px #2ea8ff20; }
.password-control.has-error { border-color: #ffb1b8; }
.password-control input { flex: 1; min-width: 0; width: 100%; border: 0; background: transparent; box-shadow: none; border-radius: 9px; padding: 14px; font-size: 16px; text-align: start; }
.password-control input:focus-visible { outline-offset: -3px; }
.password-toggle { display: inline-flex; align-items: center; justify-content: center; gap: 7px; min-width: 82px; min-height: 48px; flex-shrink: 0; border: 0; border-radius: 6px; background: transparent; color: #bce3ff; font-size: 13px; padding: 8px 12px; margin-inline-end: 3px; }
.password-toggle:hover { background: #19334c; }
.password-toggle svg { width: 20px; height: 20px; }
.password-rules { margin: 0; padding: 0; list-style: none; display: grid; gap: 4px; font-size: 13px; color: var(--muted); font-weight: 400; }
.password-rules li { display: flex; align-items: baseline; gap: 8px; line-height: 1.5; }
.password-rules .met, .password-match { color: #8de1c5; }
.password-help:empty { display: none; }
.password-help p { margin: 7px 0 0; font-size: 13px; line-height: 1.5; }
.password-error { color: #ffb1b8; }
.password-caps { color: #f3d28b; }
</style>
