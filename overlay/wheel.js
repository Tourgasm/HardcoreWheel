// ============================================================================
// DRAGGABLE ELEMENTS SETUP
// ============================================================================
function makeElementDraggable(elementId, storageKey) {
  const element = document.getElementById(elementId);
  if (!element) return;

  let offsetX = 0, offsetY = 0, mouseX = 0, mouseY = 0;

  // Load saved position from localStorage
  const saved = localStorage.getItem(storageKey);
  if (saved) {
    try {
      const pos = JSON.parse(saved);
      element.style.position = "fixed";
      element.style.left = pos.x + "px";
      element.style.top = pos.y + "px";
    } catch {
      element.style.position = "fixed";
    }
  } else {
    element.style.position = "fixed";
  }

  // Make cursor draggable
  element.style.cursor = "move";

  // Mouse down - start dragging
  element.addEventListener("mousedown", (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    offsetX = element.offsetLeft;
    offsetY = element.offsetTop;

    const onMouseMove = (moveEvent) => {
      const deltaX = moveEvent.clientX - mouseX;
      const deltaY = moveEvent.clientY - mouseY;

      element.style.left = offsetX + deltaX + "px";
      element.style.top = offsetY + deltaY + "px";
    };

    const onMouseUp = () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);

      // Save position to localStorage
      localStorage.setItem(
        storageKey,
        JSON.stringify({
          x: parseInt(element.style.left || "0", 10),
          y: parseInt(element.style.top || "0", 10),
        })
      );
    };

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  });
}

// Safe DOM helpers (OBS-safe)
function $(id) {
  return document.getElementById(id);
}
function setText(id, text) {
  const el = $(id);
  if (el) el.innerText = text;
}
function setHTML(id, html) {
  const el = $(id);
  if (el) el.innerHTML = html;
}
function setDisplay(id, value) {
  const el = $(id);
  if (el) el.style.display = value;
}

// Initialize draggable elements when page loads
document.addEventListener("DOMContentLoaded", () => {
  makeElementDraggable("wheel-container", "wheelPosition");
  makeElementDraggable("spin-bank", "spinBankPosition");
  makeElementDraggable("mini-wheel-container", "miniWheelPosition"); // ✅ added
});

// ============================================================================
// PAUSE STATUS (shown inside the Spin Bank)
// ============================================================================
const pauseStatusEl = $("pause-status");
const spinBankEl = $("spin-bank");

function normalizePauseReason(reason) {
  const r = String(reason || "").trim().toLowerCase();
  if (!r) return "unknown";
  // Common aliases coming from the server/mod
  if (r === "world_end" || r === "world ended" || r === "worldended") return "world_end";
  if (r === "apocalypse" || r === "doom" || r === "doomsday") return "apocalypse";
  if (r === "destroy_world" || r === "destroy world") return "destroy_world";
  if (r === "manual" || r === "user" || r === "ui") return "manual";
  return r;
}

function pauseLabel(reasonKey) {
  switch (reasonKey) {
    case "manual":
      return "⏸️ PAUSED (Manual)";
    case "world_end":
      return "⏸️ PAUSED (World Ended)";
    case "destroy_world":
      return "⏸️ PAUSED (Destroy World)";
    case "apocalypse":
      return "⏸️ PAUSED (Apocalypse)";
    default:
      return "⏸️ PAUSED";
  }
}

function setPaused(reason) {
  const key = normalizePauseReason(reason);
  if (pauseStatusEl) {
    pauseStatusEl.style.display = "block";
    pauseStatusEl.textContent = pauseLabel(key);
    // Reset reason classes
    pauseStatusEl.classList.remove("manual", "world_end", "apocalypse", "destroy_world");
    pauseStatusEl.classList.add(key);
  }
  if (spinBankEl) spinBankEl.classList.add("paused");
}

function clearPaused() {
  if (pauseStatusEl) {
    pauseStatusEl.style.display = "none";
    pauseStatusEl.textContent = "⏸️ PAUSED";
    pauseStatusEl.classList.remove("manual", "world_end", "apocalypse", "destroy_world");
  }
  if (spinBankEl) spinBankEl.classList.remove("paused");
}

// ============================================================================
// MAIN WHEEL SETUP
// ============================================================================
const canvas = $("wheel");
const ctx = canvas?.getContext("2d");

const label = $("label");
const targetLabel = $("target");

const SLOTS = [
  { id: "NO_ARMOR", label: "No Armor", color: "#e74c3c" },
  { id: "NO_TOOLS", label: "No Tools", color: "#e67e22" },
  { id: "LOSE_INVENTORY", label: "Lose Inventory", color: "#c0392b" },
  { id: "WOODEN_TOOLS", label: "Wooden Tools", color: "#d35400" },
  { id: "NO_EATING", label: "No Eating", color: "#f39c12" },
  { id: "WHEEL_DISCOUNT", label: "WHEEL DISCOUNT", color: "#f1c40f" },
  { id: "CLEANSE", label: "Cleanse", color: "#2ecc71" },
  { id: "LOSE_HOTBAR", label: "Lose Hotbar", color: "#9b59b6" },
  { id: "ONE_BLOCK_MODE", label: "One Block Mode", color: "#3498db" },
  { id: "NO_SHELTER", label: "No Shelter", color: "#2980b9" },
  { id: "SAFE", label: "Safe", color: "#27ae60" },
  { id: "DESTROY_WORLD", label: "Destroy World", color: "#000000" },
  { id: "NO_ATTACK", label: "Visitor Mode", color: "#95a5a6" },
  { id: "MLG_CHALLENGE", label: "MLG OR DIE", color: "#e74c3c" },
  { id: "CREEPER_SQUAD", label: "CREEPER SQUAD", color: "#2ecc71" },
  { id: "ZOMBIE_HORDE", label: "ZOMBIE HORDE", color: "#16a085" },
  { id: "COBWEB_TRAP", label: "COBWEB TRAP", color: "#95a5a6" },
  { id: "PHANTOM_ATTACK", label: "PHANTOM SQUAD", color: "#34495e" },
  { id: "RANDOM_STATUS", label: "RANDOM CURSE", color: "#9b59b6" },
  { id: "FOOD_SCRAMBLE", label: "FOOD ROT", color: "#27ae60" },
  { id: "WILD_TP", label: "WILD TELEPORT", color: "#8e44ad" },
  { id: "FLOOR_IS_LAVA", label: "FLOOR IS LAVA", color: "#FF0000" },
  { id: "TNT_RAIN", label: "TNT RAIN", color: "#FF6347" },
  { id: "DIMENSIONAL_CHAOS", label: "DIMENSION CHAOS", color: "#9932cc" },
  { id: "FREE_ARMOR", label: "FREE ARMOR", color: "#FFD700" },
  { id: "JAILBREAK", label: "JAILBREAK", color: "#2c3e50" },
  { id: "RANDOM_APOCALYPSE", label: "RANDOMIZER", color: "#663399" },
];

let CENTER = 0;
let RADIUS = 0;
let SLICE = 0;

const TICKER_ANGLE = -Math.PI / 2;
let currentRotation = 0;
let spinning = false;

function recalcGeometry() {
  if (!canvas) return;
  CENTER = canvas.width / 2;
  RADIUS = CENTER - 12;
  SLICE = (Math.PI * 2) / SLOTS.length;
}

recalcGeometry();

function drawWheel(rotation) {
  if (!canvas || !ctx) return;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  SLOTS.forEach((slot, i) => {
    const start = rotation + i * SLICE;
    const end = start + SLICE;

    ctx.beginPath();
    ctx.moveTo(CENTER, CENTER);
    ctx.arc(CENTER, CENTER, RADIUS, start, end);
    ctx.fillStyle = slot.color;
    ctx.fill();
    ctx.strokeStyle = "#000";
    ctx.stroke();

    ctx.save();
    ctx.translate(CENTER, CENTER);
    ctx.rotate(start + SLICE / 2);
    ctx.textAlign = "right";
    ctx.fillStyle = "#fff";
    ctx.font = "12px sans-serif";
    ctx.fillText(slot.label, RADIUS - 10, 6);
    ctx.restore();
  });
}

drawWheel(currentRotation);

// Tick sound
let lastPlayedSlice = -1;
const tickSound = $("tickSound");

// ============================================================================
// SPIN LOGIC
// ============================================================================
function spinTo(actionId, targets = [], meta = {}) {
  if (spinning) return;
  spinning = true;

  if (label) label.style.opacity = 0;
  if (targetLabel) targetLabel.style.opacity = 0;

  const index = SLOTS.findIndex((s) => s.id === actionId);
  if (index === -1) {
    console.warn("Unknown wheel action:", actionId);
    spinning = false;
    return;
  }

  const sliceCenter = index * SLICE + SLICE / 2;
  const rotationNeeded = TICKER_ANGLE - sliceCenter;

  const targetRotation =
    currentRotation +
    5 * Math.PI * 2 +
    (rotationNeeded - (currentRotation % (Math.PI * 2)));

  const startRotation = currentRotation;
  const startTime = performance.now();

  function animate(now) {
    const t = Math.min((now - startTime) / 4000, 1);
    const eased = 1 - Math.pow(1 - t, 3);

    currentRotation = startRotation + eased * (targetRotation - startRotation);

    // Tick sound logic
    const normalizedRotation =
      ((currentRotation % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);

    const currentSliceAtTicker = Math.floor(
      (((TICKER_ANGLE - normalizedRotation + Math.PI * 2) % (Math.PI * 2)) /
        SLICE)
    );

    if (currentSliceAtTicker !== lastPlayedSlice) {
      if (tickSound) {
        try {
          tickSound.currentTime = 0;
          tickSound.play().catch(() => {});
        } catch {}
      }
      lastPlayedSlice = currentSliceAtTicker;
    }

    drawWheel(currentRotation);

    if (t < 1) {
      requestAnimationFrame(animate);
      return;
    }

    // finish
    currentRotation =
      ((targetRotation % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);

    if (label) {
      label.innerText = SLOTS[index].label;
      label.style.opacity = 1;
    }

    if (targetLabel) {
      targetLabel.innerText =
        Array.isArray(targets) && targets.length ? targets.join(" & ") : "";
      targetLabel.style.opacity = 1;
    }

    spinning = false;
    lastPlayedSlice = -1;

    // ✅ LOSE_HOTBAR handling - show slot + spin mini wheel (OBS-safe)
    if (actionId === "LOSE_HOTBAR") {
      const slot = meta?.slot ?? "ALL";

      if (targetLabel) {
        targetLabel.innerText =
          String(slot).toUpperCase() === "ALL"
            ? "HOTBAR: ALL SLOTS"
            : `HOTBAR SLOT ${slot}`;
        targetLabel.style.opacity = 1;
      }

      try {
        if (typeof window.spinMiniWheel === "function") {
          window.spinMiniWheel(slot);
        }
      } catch (e) {
        console.warn("Mini wheel failed:", e);
      }
    }
  }

  requestAnimationFrame(animate);
}

// ============================================================================
// WEBSOCKET OVERLAY EVENTS
// ============================================================================
const socket = new WebSocket("ws://localhost:5760");

socket.onopen = () => {
  // console.log("Overlay socket connected");
  // Fetch initial config on connection
  fetchServerConfig();
};

socket.onerror = (err) => {
  console.warn("Overlay socket error:", err);
};

socket.onclose = () => {
  // console.warn("Overlay socket closed");
  // Retry connection every 5 seconds
  setTimeout(() => {
    location.reload();
  }, 5000);
};

// ============================================================================
// REAL-TIME CONFIG FETCHING
// ============================================================================
async function fetchServerConfig() {
  // Fetch current server config from Flask API
  try {
    const response = await fetch("http://localhost:3000/config");
    if (!response.ok) return;
    
    const data = await response.json();
    if (!data.ok) return;
    
    // Update all config values
    if (data.PRICE_PER_SPIN !== undefined) {
      setText("base-price", data.PRICE_PER_SPIN.toFixed(2));
    }
    if (data.REVIVE_PRICE !== undefined) {
      setText("revive-price", data.REVIVE_PRICE.toFixed(2));
    }
    if (data.REVIVE_POINTS_COST !== undefined) {
      setText("revive-points", String(data.REVIVE_POINTS_COST));
    }
  } catch (err) {
    console.warn("Config fetch error:", err);
  }
}

// Fetch config every 5 seconds to stay in sync
setInterval(fetchServerConfig, 5000);

// Format seconds to MM:SS
function formatTime(seconds) {
  const s = Math.max(0, Math.floor(Number(seconds) || 0));
  const mins = Math.floor(s / 60);
  const secs = s % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

socket.onmessage = (event) => {
  let data;
  try {
    data = JSON.parse(event.data);
  } catch (e) {
    console.warn("Bad overlay JSON:", e);
    return;
  }

  if (!data?.type) return;

  if (data.type === "UPDATE_QUEUE") {
    setText("queue-count", data.count ?? "");
    setText("next-donor", data.nextUp ?? "");

    // Update base price if provided
    if (data.basePrice !== undefined) {
      setText("base-price", (Number(data.basePrice) || 2.0).toFixed(2));
    }

    // Update revival price if provided
    if (data.revivePrice !== undefined) {
      setText("revive-price", (Number(data.revivePrice) || 5.0).toFixed(2));
    }

    // Update revive points cost if provided
    if (data.revivePointsCost !== undefined) {
      setText("revive-points", String(parseInt(data.revivePointsCost, 10) || 1000));
    }

    // Top donors
    const topDonorsList = $("top-donors-list");
    if (topDonorsList && Array.isArray(data.topDonors)) {
      topDonorsList.innerHTML = "";
      data.topDonors.forEach((donor, index) => {
        const li = document.createElement("li");
        const medal = index === 0 ? "🥇" : index === 1 ? "🥈" : "🥉";
        const total = Number(donor.total || 0);
        li.innerHTML = `${medal} <strong>${donor.name}:</strong> $${total.toFixed(2)}`;
        topDonorsList.appendChild(li);
      });
    }

    // Top killers
    const topKillersList = $("top-killers-list");
    if (topKillersList && Array.isArray(data.topKillers)) {
      topKillersList.innerHTML = "";
      data.topKillers.forEach((killer, index) => {
        const li = document.createElement("li");
        const medal = index === 0 ? "💀" : index === 1 ? "💀" : "💀";
        const kills = Number(killer.kills || 0);
        li.innerHTML = `${medal} <strong>${killer.name}:</strong> ${kills} kills`;
        topKillersList.appendChild(li);
      });
    }

    // History
    const historyList = $("history-list");
    if (historyList && Array.isArray(data.history)) {
      historyList.innerHTML = "";
      data.history.forEach((item) => {
        const li = document.createElement("li");
        const action = String(item.action || "").replaceAll("_", " ");
        li.innerHTML = `<strong>${item.donor}:</strong> ${action}`;
        historyList.appendChild(li);
      });
    }

    // Pause status can be sent in the queue update (useful on initial connect)
    if (data.paused === true) {
      setPaused(data.pauseReason ?? data.pause_reason ?? data.reason ?? "unknown");
    } else if (data.paused === false) {
      clearPaused();
    }
  }

  if (data.type === "WHEEL_PAUSED") {
    setPaused(data.reason ?? data.pauseReason ?? data.pause_reason ?? "unknown");
  }

  if (data.type === "WHEEL_RESUMED") {
    clearPaused();
  }

  if (data.type === "UPDATE_LEADERBOARD") {
    const topKillersList = $("top-killers-list");
    if (topKillersList && Array.isArray(data.killers)) {
      topKillersList.innerHTML = "";
      data.killers.forEach((killer, index) => {
        const li = document.createElement("li");
        const medal = index === 0 ? "🥇" : index === 1 ? "🥈" : "🥉";
        li.innerHTML = `${medal} <strong>${killer.name}:</strong> ${
          killer.kills ?? 0
        } 💀`;
        topKillersList.appendChild(li);
      });
    }
  }

  if (data.type === "discount") {
    if (label) {
      label.innerText = data.message ?? "DISCOUNT!";
      label.style.opacity = 1;
      label.style.fontSize = "48px";
      label.style.color = "#FFD700";
      label.style.textShadow = "0 0 20px #FFD700, 0 0 40px #FFA500";
      label.style.animation = "pulse 0.5s ease-in-out 3";
      setTimeout(() => {
        if (label) label.style.opacity = 0;
      }, 3000);
    }

    setDisplay("discount-timer", "block");
    setText("discount-time", formatTime(data.remaining));
    setText("discount-price", data.price ?? "1.0");
  }

  if (data.type === "discount_timer") {
    setDisplay("discount-timer", "block");
    setText("discount-time", formatTime(data.remaining));
    setText("discount-price", data.price ?? "1.0");
  }

  if (data.type === "discount_ended") {
    setDisplay("discount-timer", "none");
  }

  if (data.type === "price_update") {
    // Real-time base price update
    if (data.basePrice !== undefined) {
      setText("base-price", (Number(data.basePrice) || 2.0).toFixed(2));
    }
  }

  if (data.type === "revive_points_update") {
    if (data.revivePointsCost !== undefined) {
      setText("revive-points", String(parseInt(data.revivePointsCost, 10) || 1000));
    }
  }

  if (data.type === "discount_update") {
    // Real-time discount price update
    if (data.discountPrice !== undefined) {
      setText("discount-price", (Number(data.discountPrice) || 1.0).toFixed(2));
    }
  }

  if (data.type === "config_update") {
    // Real-time config update from server
    if (data.basePrice !== undefined) {
      setText("base-price", (Number(data.basePrice) || 2.0).toFixed(2));
    }
    if (data.revivePrice !== undefined) {
      setText("revive-price", (Number(data.revivePrice) || 5.0).toFixed(2));
    }
    if (data.revivePointsCost !== undefined) {
      setText("revive-points", String(parseInt(data.revivePointsCost, 10) || 1000));
    }
    if (data.discountPrice !== undefined) {
      setText("discount-price", (Number(data.discountPrice) || 1.0).toFixed(2));
    }
  }

  if (data.type === "revive_price_update") {
    // Real-time revive price update
    if (data.revivePrice !== undefined) {
      setText("revive-price", (Number(data.revivePrice) || 5.0).toFixed(2));
    }
    if (data.revivePointsCost !== undefined) {
      setText("revive-points", String(parseInt(data.revivePointsCost, 10) || 1000));
    }
  }

  if (data.type === "WHEEL_PAUSED") {
    setPaused(data.reason ?? "unknown");
  }

  if (data.type === "WHEEL_RESUMED") {
    clearPaused();
  }

  if (data.type === "disabled_punishments_update") {
    // Real-time disabled punishments update - rebuild wheel with filtered slots
    if (Array.isArray(data.disabled_punishments)) {
      // Define all slots
      const ALL_SLOTS = [
        { id: "NO_ARMOR", label: "No Armor", color: "#e74c3c" },
        { id: "NO_TOOLS", label: "No Tools", color: "#e67e22" },
        { id: "LOSE_INVENTORY", label: "Lose Inventory", color: "#c0392b" },
        { id: "WOODEN_TOOLS", label: "Wooden Tools", color: "#d35400" },
        { id: "NO_EATING", label: "No Eating", color: "#f39c12" },
        { id: "WHEEL_DISCOUNT", label: "WHEEL DISCOUNT", color: "#f1c40f" },
        { id: "CLEANSE", label: "Cleanse", color: "#2ecc71" },
        { id: "LOSE_HOTBAR", label: "Lose Hotbar", color: "#9b59b6" },
        { id: "ONE_BLOCK_MODE", label: "One Block Mode", color: "#3498db" },
        { id: "NO_SHELTER", label: "No Shelter", color: "#2980b9" },
        { id: "SAFE", label: "Safe", color: "#27ae60" },
        { id: "DESTROY_WORLD", label: "Destroy World", color: "#000000" },
        { id: "NO_ATTACK", label: "Visitor Mode", color: "#95a5a6" },
        { id: "MLG_CHALLENGE", label: "MLG OR DIE", color: "#e74c3c" },
        { id: "CREEPER_SQUAD", label: "CREEPER SQUAD", color: "#2ecc71" },
        { id: "ZOMBIE_HORDE", label: "ZOMBIE HORDE", color: "#16a085" },
        { id: "COBWEB_TRAP", label: "COBWEB TRAP", color: "#95a5a6" },
        { id: "PHANTOM_ATTACK", label: "PHANTOM SQUAD", color: "#34495e" },
        { id: "RANDOM_STATUS", label: "RANDOM CURSE", color: "#9b59b6" },
        { id: "FOOD_SCRAMBLE", label: "FOOD ROT", color: "#27ae60" },
        { id: "WILD_TP", label: "WILD TELEPORT", color: "#8e44ad" },
        { id: "FLOOR_IS_LAVA", label: "FLOOR IS LAVA", color: "#FF0000" },
        { id: "TNT_RAIN", label: "TNT RAIN", color: "#FF6347" },
        { id: "DIMENSIONAL_CHAOS", label: "DIMENSION CHAOS", color: "#9932cc" },
        { id: "FREE_ARMOR", label: "FREE ARMOR", color: "#FFD700" },
        { id: "JAILBREAK", label: "JAILBREAK", color: "#2c3e50" },
        { id: "RANDOM_APOCALYPSE", label: "RANDOMIZER", color: "#663399" }
      ];
      
      // Filter out disabled punishments
      SLOTS.length = 0;
      ALL_SLOTS.forEach(slot => {
        if (!data.disabled_punishments.includes(slot.id)) {
          SLOTS.push(slot);
        }
      });
      
      // Rebuild wheel with new filtered slots
      recalcGeometry();
      drawWheel(currentRotation);
    }
  }

  if (data.type === "SHOW_WHEEL") {
    if (label) label.style.opacity = 0;
    if (targetLabel) {
      targetLabel.style.opacity = 0;
      if (data.donor) {
        targetLabel.innerText = `SPIN BY: ${String(data.donor).toUpperCase()}`;
        targetLabel.style.opacity = 1;
      }
    }
    
    // Update SLOTS if server sent filtered slots
    if (Array.isArray(data.slots) && data.slots.length > 0) {
      SLOTS.length = 0; // Clear current slots
      SLOTS.push(...data.slots); // Add filtered slots
      recalcGeometry(); // Recalculate wheel geometry with new slot count
      drawWheel(currentRotation); // Redraw wheel
    }
    
    // Update base price display if provided
    if (data.basePrice !== undefined) {
      setText("base-price", (Number(data.basePrice) || 2.0).toFixed(2));
    }
    
    const wheelContainer = $("wheel-container");
    if (wheelContainer) wheelContainer.classList.add("visible");
  }

  if (data.type === "WHEEL_RESULT") {
    spinTo(data.action, data.targets, data.meta);
  }

  if (data.type === "HIDE_WHEEL") {
    const wheelContainer = $("wheel-container");
    if (wheelContainer) wheelContainer.classList.remove("visible");
  }
};
