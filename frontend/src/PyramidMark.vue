<script setup>
import { onMounted, onBeforeUnmount, shallowRef, useTemplateRef } from "vue";
import { t } from "./i18n";

const stage = useTemplateRef("stage");
const reduced = shallowRef(false);
let media, observer, frame = 0, inView = true;
let pointerX = 0, pointerY = 0, turn = 0;
function render() {
  frame = 0;
  if (!stage.value) return;
  const rect = stage.value.getBoundingClientRect();
  const progress = reduced.value ? 0 : Math.max(0, Math.min(1, -rect.top / Math.max(rect.height, 1)));
  stage.value.style.setProperty("--sculpture-turn", `${turn + progress * 64 + pointerX * 16}deg`);
  stage.value.style.setProperty("--sculpture-tilt", `${pointerY * -6}deg`);
  stage.value.style.setProperty("--layer-spread", `${progress * 18}px`);
}
function schedule() { if (inView && !frame) frame = requestAnimationFrame(render); }
function point(event) {
  if (reduced.value || event.pointerType !== "mouse") return;
  const rect = stage.value.getBoundingClientRect();
  pointerX = (event.clientX - rect.left) / rect.width - .5;
  pointerY = (event.clientY - rect.top) / rect.height - .5;
  schedule();
}
function resetPointer() { pointerX = pointerY = 0; schedule(); }
function rotate() { turn += 90; schedule(); }
function preference() { reduced.value = media.matches; resetPointer(); }
onMounted(() => {
  media = matchMedia("(prefers-reduced-motion: reduce)");
  preference();
  media.addEventListener("change", preference);
  window.addEventListener("scroll", schedule, { passive: true });
  observer = new IntersectionObserver(([entry]) => { inView = entry.isIntersecting; if (inView) schedule(); });
  observer.observe(stage.value);
});
onBeforeUnmount(() => {
  cancelAnimationFrame(frame);
  observer?.disconnect();
  media?.removeEventListener("change", preference);
  window.removeEventListener("scroll", schedule);
});
</script>

<template>
  <div class="learning-sculpture">
    <div ref="stage" class="pyramid-stage" aria-hidden="true" @pointermove="point" @pointerleave="resetPointer">
      <div class="foundation foundation-bottom"></div>
      <div class="foundation foundation-middle"></div>
      <div class="foundation foundation-top"></div>
      <div class="pyramid-scene">
        <div class="pyramid-arrival">
          <div class="pyramid-turntable">
            <div class="pyramid-solid">
              <i class="pyramid-face face-front"></i><i class="pyramid-face face-right"></i>
              <i class="pyramid-face face-back"></i><i class="pyramid-face face-left"></i>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="sculpture-caption">
      <span>{{ t("Learn. Practise. Build.") }}</span>
      <button type="button" class="sculpture-rotate" @click="rotate" :aria-label="t('Rotate the pyramid')" :title="t('Rotate the pyramid')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.2 6.2A8 8 0 0 1 20 12M4 12a8 8 0 0 0 13.8 5.8"/></svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.learning-sculpture { width: 100%; max-width: 440px; justify-self: center; }
.pyramid-stage { position: relative; width: 100%; height: 350px; display: grid; place-items: center; perspective: 1000px; }
.pyramid-scene { position: relative; width: 180px; height: 180px; perspective: 920px; transform: translateY(-32px) scale(1.65); z-index: 2; }
.pyramid-arrival { position: absolute; inset: 0; transform-style: preserve-3d; animation: sculpture-arrive 1.65s cubic-bezier(.2,.75,.25,1) both; }
.pyramid-turntable { position: absolute; inset: 0; transform-style: preserve-3d; transform: rotateX(var(--sculpture-tilt, 0deg)) rotateY(var(--sculpture-turn, 0deg)); transition: transform .7s cubic-bezier(.18,.8,.25,1); }
.pyramid-solid { position: absolute; inset: 7px 10px 13px; transform-style: preserve-3d; transform: rotateX(-18deg) rotateY(55deg); }
.pyramid-face { position: absolute; top: 6px; left: 18px; width: 124px; height: 122px; display: block; clip-path: polygon(50% 0,100% 100%,0 100%); transform-origin: 50% 100%; backface-visibility: hidden; border-bottom: 1px solid #c9e7ff70; }
.face-front { background: linear-gradient(148deg,#9be8ff 0%,#328fff 45%,#1742a6 100%); transform: rotateY(0deg) translateZ(62px) rotateX(30.5deg); }
.face-right { background: linear-gradient(145deg,#b0adff 0%,#6258d8 48%,#2d267e 100%); transform: rotateY(90deg) translateZ(62px) rotateX(30.5deg); }
.face-back { background: linear-gradient(145deg,#638be1,#162864 78%); transform: rotateY(180deg) translateZ(62px) rotateX(30.5deg); }
.face-left { background: linear-gradient(145deg,#b5ffeb 0%,#37b7b5 48%,#155373 100%); transform: rotateY(-90deg) translateZ(62px) rotateX(30.5deg); }
.foundation { position: absolute; top: 95px; width: 238px; height: 238px; border: 1px solid #5aabd15e; background: linear-gradient(135deg,#1c485459,#102a4377); transform: translateY(var(--plate-offset)) rotateX(64deg) rotateZ(-35deg); box-shadow: 9px 14px 0 #04101d, 10px 15px 0 #2c60754d; transition: transform .5s ease; }
.foundation-top { --plate-offset: calc(-18px - var(--layer-spread, 0px)); background: linear-gradient(135deg,#2c5c6b80,#16344a80); }
.foundation-middle { --plate-offset: 8px; }
.foundation-bottom { --plate-offset: calc(34px + var(--layer-spread, 0px)); opacity: .5; }
.sculpture-caption { display: flex; justify-content: center; align-items: center; gap: 18px; margin-top: 8px; font-size: 13px; color: #b8cadc; }
.sculpture-rotate { display: grid; place-items: center; width: 44px; height: 44px; border: 1px solid #426078; border-radius: 12px; background: transparent; color: #bde8f4; transition: background .2s; }
.sculpture-rotate:hover { background: #18334a; }
.sculpture-rotate svg { width: 21px; height: 21px; }
@keyframes sculpture-arrive { from { transform: rotateY(-75deg) translateY(-12px); } to { transform: none; } }
@media (max-width: 760px) {
  .learning-sculpture { max-width: 300px; }
  .pyramid-stage { height: 250px; }
  .pyramid-scene { transform: translateY(-25px) scale(1.12); }
  .foundation { top: 60px; width: 178px; height: 178px; }
  .sculpture-caption { margin-top: 4px; }
}
@media (prefers-reduced-motion: reduce) {
  .pyramid-arrival { animation: none; }
  .pyramid-turntable, .foundation { transition: none; }
}
</style>
