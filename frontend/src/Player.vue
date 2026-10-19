<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import shaka from "shaka-player/dist/shaka-player.ui.js";
import "shaka-player/dist/controls.css";
import { rpc } from "./api";
const props = defineProps({ lesson: String });
const video = ref(),
  container = ref(),
  error = ref(""),
  watermark = ref(""),
  loading = ref(true),
  position = ref({ left: "6%", top: "12%" });
let player,
  ui,
  grant,
  refresh,
  tick,
  move,
  dead = false,
  last = -1;
async function save(event = "heartbeat", allowPaused = false) {
  if (
    !video.value ||
    !grant ||
    video.value.currentTime === last ||
    (video.value.paused && event !== "ended" && !allowPaused)
  )
    return;
  last = video.value.currentTime;
  try {
    await rpc(
      "video.heartbeat",
      { lesson: props.lesson, position: last, event },
      true,
    );
  } catch (e) {
    error.value = e.message;
  }
}
onMounted(async () => {
  try {
    shaka.polyfill.installAll();
    if (!shaka.Player.isBrowserSupported())
      throw new Error(
        "This browser cannot play this video. Try a current Firefox, Chrome, or Safari browser.",
      );
    grant = await rpc("video.authorize", { lesson: props.lesson }, true);
    if (dead) return;
    watermark.value = grant.watermark;
    player = new shaka.Player();
    await player.attach(video.value);
    if (dead) return;
    ui = new shaka.ui.Overlay(player, container.value, video.value);
    ui.configure({
      controlPanelElements: [
        "play_pause",
        "time_and_duration",
        "spacer",
        "mute",
        "volume",
        "overflow_menu",
        "fullscreen",
      ],
      overflowMenuButtons: ["playback_rate", "quality", "captions"],
    });
    player.getNetworkingEngine().registerRequestFilter((_type, request) => {
      request.allowCrossSiteCredentials = true;
      request.uris = request.uris.map((uri) => {
        const url = new URL(uri, location.origin);
        if (
          url.origin !== location.origin ||
          url.pathname !== "/api/method/nightjar_learning.video.resource"
        )
          throw new Error("Unexpected media origin");
        url.searchParams.set("token", grant.token);
        return url.toString();
      });
    });
    player.addEventListener("error", () => {
      error.value = "Playback stopped. Reload the lesson to renew access.";
    });
    await player.load(
      grant.manifest,
      grant.position >= grant.duration - 2 ? 0 : grant.position,
      "application/x-mpegurl",
    );
    if (dead) return;
    loading.value = false;
    refresh = setInterval(async () => {
      try {
        grant = await rpc("video.authorize", { lesson: props.lesson }, true);
      } catch (e) {
        error.value = e.message;
        video.value?.pause();
      }
    }, 180000);
    tick = setInterval(() => save(), 15000);
    move = setInterval(() => {
      position.value = {
        left: `${6 + Math.random() * 48}%`,
        top: `${8 + Math.random() * 52}%`,
      };
    }, 20000);
  } catch (e) {
    loading.value = false;
    error.value = e.message;
  }
});
onBeforeUnmount(() => {
  save("heartbeat", true);
  dead = true;
  clearInterval(refresh);
  clearInterval(tick);
  clearInterval(move);
  ui?.destroy();
  player?.destroy();
});
</script>
<template>
  <div ref="container" class="video-shell">
    <video
      ref="video"
      playsinline
      preload="metadata"
      @ended="save('ended')"
      @pause="save('heartbeat', true)"
      aria-label="Lesson video"
    ></video>
    <div class="watermark" :style="position" aria-hidden="true">
      {{ watermark }}
    </div>
    <div v-if="loading" class="player-status">Preparing your lesson…</div>
  </div>
  <p v-if="error" class="notice error" role="alert">{{ error }}</p>
</template>
