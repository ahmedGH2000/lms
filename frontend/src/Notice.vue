<script setup>
defineOptions({ inheritAttrs: false });
defineProps({ message: String, kind: { type: String, default: "success" } });
defineEmits(["dismiss"]);
</script>
<template>
  <Transition name="notice">
    <div v-bind="$attrs" v-if="message" :key="message" class="notice notice-polished" :class="kind" :role="kind === 'error' ? 'alert' : 'status'">
      <span class="notice-icon" aria-hidden="true">{{ kind === 'error' ? '!' : '✓' }}</span>
      <span>{{ message }}</span>
      <button type="button" class="notice-dismiss" aria-label="Dismiss notification" @click="$emit('dismiss')">×</button>
    </div>
  </Transition>
</template>
