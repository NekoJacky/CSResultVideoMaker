/* 公共工具：缓动、时间轴进度、数字滚动、幕内淡入淡出。
   所有动效必须由 renderFrame(t) 驱动，禁止 rAF / setTimeout / CSS 动画。 */

window.clamp = (v, a, b) => Math.min(b, Math.max(a, v));
window.lerp = (a, b, p) => a + (b - a) * p;
window.easeOutCubic = (p) => 1 - Math.pow(1 - p, 3);
window.easeInOut = (p) =>
  p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;

/* 在 [start, start + dur] 区间内把 0..1 映射到 a..b。 */
window.prog = (t, start, dur) => window.clamp((t - start) / dur, 0, 1);

/* 数字滚动：从 0 滚到 target（p 为 0..1 的进度）。 */
window.setNumber = (el, value, p, decimals = 0) => {
  el.textContent = (value * window.easeOutCubic(p)).toFixed(decimals);
};

/* 全幕统一的淡入淡出（避免幕间转场）。 */
window.fadeWrap = (el, t, duration, fade = 0.4) => {
  const inP = window.prog(t, 0, fade);
  const outP = window.prog(t, duration - fade, fade);
  el.style.opacity = Math.min(inP, 1 - outP);
};
