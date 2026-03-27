(() => {
  "use strict";

  // Slots: 1-9 plus ALL
  const MINI_SLOTS = [1, 2, 3, 4, 5, 6, 7, 8, 9, "ALL"];
  const MINI_SLICE = (Math.PI * 2) / MINI_SLOTS.length;

  const SPIN_DURATION_MS = 1800;   // smooth but quick
  const HIDE_DELAY_MS = 1800;      // after landing

  let miniRotation = 0;
  let miniSpinning = false;
  let rafId = 0;
  let hideTimer = 0;

  function $(id) {
    return document.getElementById(id);
  }

  function getCtx() {
    const canvas = $("miniWheel");
    if (!canvas) return null;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;

    const size = Math.min(canvas.width, canvas.height);
    const center = size / 2;
    const radius = center - 10;

    return { canvas, ctx, center, radius };
  }

  function showMini() {
    const container = $("mini-wheel-container");
    if (container) container.style.display = "block";
  }

  function hideMini() {
    const container = $("mini-wheel-container");
    if (container) container.style.display = "none";
  }

  function normalizeSlot(slot) {
    // Accept: 1..9, "ALL", "1".."9", 0..8 (map to 1..9)
    if (slot === undefined || slot === null) return "ALL";

    // string numeric
    if (typeof slot === "string") {
      const s = slot.trim().toUpperCase();
      if (s === "ALL") return "ALL";
      const n = parseInt(s, 10);
      if (!Number.isNaN(n)) slot = n;
    }

    if (typeof slot === "number") {
      // handle 0..8
      if (slot >= 0 && slot <= 8) return slot + 1;
      // handle 1..9
      if (slot >= 1 && slot <= 9) return slot;
    }

    return "ALL";
  }

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function drawMiniWheel(rotation) {
    const env = getCtx();
    if (!env) return;

    const { canvas, ctx, center, radius } = env;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw slices
    for (let i = 0; i < MINI_SLOTS.length; i++) {
      const label = MINI_SLOTS[i];
      const a0 = i * MINI_SLICE + rotation;
      const a1 = a0 + MINI_SLICE;

      ctx.beginPath();
      ctx.moveTo(center, center);
      ctx.arc(center, center, radius, a0, a1);
      ctx.closePath();

      // Alternate slightly for readability (no fancy colors needed)
      ctx.fillStyle = (i % 2 === 0) ? "#2b2b2b" : "#3a3a3a";
      ctx.fill();
      ctx.strokeStyle = "#000";
      ctx.lineWidth = 2;
      ctx.stroke();

      // Text
      ctx.save();
      ctx.translate(center, center);
      ctx.rotate(a0 + MINI_SLICE / 2);
      ctx.textAlign = "right";
      ctx.fillStyle = "#fff";
      ctx.font = "bold 16px sans-serif";
      ctx.fillText(String(label), radius - 12, 6);
      ctx.restore();
    }

    // Pointer at top (tiny triangle)
    ctx.save();
    ctx.translate(center, center);
    ctx.fillStyle = "#ff3b3b";
    ctx.beginPath();
    ctx.moveTo(0, -radius - 4);
    ctx.lineTo(-10, -radius + 16);
    ctx.lineTo(10, -radius + 16);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  function computeTargetRotationForIndex(index, extraSpins) {
    // We want the *center* of the chosen slice to land at the top pointer.
    // Pointer is at angle -PI/2.
    const sliceCenter = index * MINI_SLICE + MINI_SLICE / 2;

    // Solve: sliceCenter + rotation == -PI/2  (mod 2PI)
    // => rotation == -PI/2 - sliceCenter
    const desired = (-Math.PI / 2) - sliceCenter;

    // Add spins backwards to make it animate nicely
    return desired - extraSpins * Math.PI * 2;
  }

  function spinMiniWheel(slot) {
    const normalized = normalizeSlot(slot);

    // If it's already spinning, ignore (prevents double-RAF explosions)
    if (miniSpinning) return;

    const index = MINI_SLOTS.indexOf(normalized);
    if (index === -1) return;

    // clear any previous timers/raf
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = 0;

    miniSpinning = true;
    showMini();

    const startRot = miniRotation;
    const endRot = computeTargetRotationForIndex(index, 3); // 3 full spins
    const startTime = performance.now();

    const animate = (now) => {
      const t = Math.min((now - startTime) / SPIN_DURATION_MS, 1);
      const eased = easeOutCubic(t);

      miniRotation = startRot + eased * (endRot - startRot);
      drawMiniWheel(miniRotation);

      if (t < 1) {
        rafId = requestAnimationFrame(animate);
      } else {
        rafId = 0;
        miniSpinning = false;

        hideTimer = setTimeout(() => {
          hideMini();
        }, HIDE_DELAY_MS);
      }
    };

    // draw immediately so it appears instantly
    drawMiniWheel(miniRotation);
    rafId = requestAnimationFrame(animate);
  }

  // Expose globally for wheel.js
  window.spinMiniWheel = spinMiniWheel;

  // Optional: draw once on load (won't show unless container visible)
  document.addEventListener("DOMContentLoaded", () => {
    drawMiniWheel(miniRotation);
  });
})();
