/**
 * hardcore.js - Hardcore mode system for the apocalypse
 * Handles death tracking, lives system, and world escalation
 */

import { world, system } from "@minecraft/server";
import { requestRevival } from "./revival.js";
import { initializeDeathEventManager, subscribeToDeaths } from "./lib/deathEventManager.js";

const LIVES_PER_PLAYER = 5; // Default lives per player (can be overridden by config)
const DIFFICULTY_PHASE = 5;
// Default world-end threshold (can be overridden live by the Wheel Server)
let worldEndPhase = 20;
let hardcoreModeEnabled = true;  // Toggle for hardcore world (world end + lives)
const LOCK_TAG = "hardcore_locked";

let worldEnded = false;
let totalDeaths = 0;
const playerLives = new Map(); // Track lives per player

/* ======================================================
   SCRIPT EVENT LISTENER (for Python server commands)
====================================================== */

function registerScriptEventListener() {
  system.afterEvents.scriptEventReceive.subscribe(event => {
    // Only listen to wheel:run events from the Python server
    if (event.id !== "wheel:run") return;
    if (event.sourceType !== "Server" && event.sourceType !== "External") return;
    
    try {
      const data = JSON.parse(event.message);

      // Handle config updates from the Wheel Server
      if (data.type === "config" && data.action === "SET_WORLD_END_DEATHS") {
        const raw = Number(data.value);
        const clamped = Math.max(20, Math.min(150, Math.floor(isFinite(raw) ? raw : 20)));

        worldEndPhase = clamped;
        console.warn(`[Hardcore] World end threshold updated: ${worldEndPhase} deaths`);
        return;
      }

      // Handle hardcore mode toggle from the Wheel Server
      if (data.type === "config" && data.action === "SET_HARDCORE_MODE") {
        hardcoreModeEnabled = Boolean(data.value);
        console.warn(`[Hardcore] Hardcore mode: ${hardcoreModeEnabled ? "ON" : "OFF"}`);
        return;
      }
      
      // Handle revival command from Python server
      if (data.type === "revival" && data.action === "REVIVAL") {
        const playerName = data.player || "@a";
        const donorName = data.donor || "Anonymous";
        const amount = data.amount || 0;
        
        console.log(`[REVIVAL EVENT] Player: ${playerName}, Donor: ${donorName}, Amount: $${amount}`);
        requestRevival(playerName, donorName, amount);
      }
    } catch (e) {
      console.warn(`[Script Event] Error parsing wheel:run message: ${e.message}`);
      console.warn(`[Script Event] Raw message was: "${event.message}"`);
    }
  });
}

/* ======================================================
   INITIALIZATION
====================================================== */

function initializeHardcore() {
  system.run(() => {
    const overworld = world.getDimension("overworld");

    // Disable command feedback
    overworld.runCommand("gamerule sendcommandfeedback false");
    overworld.runCommand("gamerule commandblockoutput false");

    // Initialize all players with 3 lives
    for (const player of world.getPlayers()) {
      if (!playerLives.has(player.name)) {
        playerLives.set(player.name, LIVES_PER_PLAYER);
      }
    }

    world.sendMessage("☠️ Hardcore World Initialized");
  });
}

/* ======================================================
   DEATH HANDLING - Uses shared death event manager
====================================================== */

function registerDeathHandler() {
  subscribeToDeaths((deadPlayer) => {
    if (worldEnded) {
      deadPlayer.addTag("hardcore_dead");
      return;
    }

    // Skip hardcore logic if hardcore mode is disabled
    if (!hardcoreModeEnabled) {
      return;
    }

    // Initialize lives if not set
    if (!playerLives.has(deadPlayer.name)) {
      playerLives.set(deadPlayer.name, LIVES_PER_PLAYER);
    }

    // Decrement lives
    let lives = playerLives.get(deadPlayer.name);
    lives--;
    playerLives.set(deadPlayer.name, lives);
    totalDeaths++;

    // Show message with total deaths and remaining lives
    if (lives > 0) {
      world.sendMessage(`§c☠ ${deadPlayer.name} has fallen (${totalDeaths}) §6Lives remaining: ${lives}`);
    } else {
      world.sendMessage(`§4☠ ${deadPlayer.name} is permanently dead! §7Total deaths: (${totalDeaths})`);
      deadPlayer.addTag("hardcore_dead");
    }

    if (totalDeaths === DIFFICULTY_PHASE) escalateDifficulty();
    if (totalDeaths === worldEndPhase) endWorld();
  });
}

/* ======================================================
   RESPAWN HANDLING
====================================================== */

function registerRespawnHandler() {
  world.afterEvents.playerSpawn.subscribe(event => {
    const player = event.player;

    // Initialize lives on first join
    if (!playerLives.has(player.name)) {
      playerLives.set(player.name, LIVES_PER_PLAYER);
    }

    // CHECK FOR REVIVAL - RESTORE 1 LIFE
    if (player.hasTag("revival_restore_lives")) {
      player.removeTag("revival_restore_lives");
      let currentLives = playerLives.get(player.name) || 0;
      currentLives = Math.min(currentLives + 1, LIVES_PER_PLAYER);
      playerLives.set(player.name, currentLives);
      world.sendMessage(`§a✨ ${player.name} has been revived! Lives: ${currentLives}/3`);
      return;
    }

    if (player.hasTag("hardcore_dead") || worldEnded) {
      system.run(() => {
        try {
          player.kick("§cHARDCORE: Death is permanent. This world is lost to you.");
        } catch (e) {
          player.runCommand("gamemode spectator @s");
        }
      });
    }
  });
}

/* ======================================================
   ACTION BAR DISPLAY (Lives Counter)
====================================================== */

function startActionBarDisplay() {
  system.runInterval(() => {
    for (const player of world.getPlayers()) {
      if (!player.hasTag("hardcore_dead") && !worldEnded) {
        const lives = playerLives.get(player.name) ?? LIVES_PER_PLAYER;
        const hearts = "❤".repeat(lives);
        player.onScreenDisplay.setActionBar(`§c${hearts} §7Lives: §6${lives}`);
      }
    }
  }, 10);
}

/* ======================================================
   ANTI-CHEAT & REJOIN PROTECTION
====================================================== */

function startAntiCheat() {
  system.runInterval(() => {
    for (const player of world.getPlayers()) {
      if (player.hasTag("hardcore_dead")) {
        try {
          player.kick("§cHARDCORE: You are currently dead.");
        } catch (e) {
          if (player.getGameMode() !== "spectator") {
            player.runCommand(`gamemode spectator "${player.name}"`);
          }
        }
      }
    }
  }, 100);
}

/* ======================================================
   PHASE ACTIONS
====================================================== */

function escalateDifficulty() {
  const overworld = world.getDimension("overworld");
  world.sendMessage("⚠️ The world grows hostile...");
  overworld.runCommand("difficulty hard");
  overworld.runCommand("weather thunder 1200");
}

function endWorld() {
  if (worldEnded) return;
  worldEnded = true;

  const overworld = world.getDimension("overworld");
  world.sendMessage("§4☠ THE WORLD IS LOST ☠");

  for (const player of world.getPlayers()) {
    if (!player.hasTag("hardcore_dead")) {
      player.addTag("hardcore_dead");
      player.runCommand("kill @s");
    }
  }

  for (let i = 0; i < 5; i++) {
    overworld.runCommand("summon minecraft:wither ~ ~5 ~");
  }
}

/* ======================================================
   MAIN STARTUP
====================================================== */

system.run(() => {
  // Initialize the shared death event manager FIRST
  initializeDeathEventManager();
  
  registerScriptEventListener();
  initializeHardcore();
  registerDeathHandler();
  registerRespawnHandler();
  startActionBarDisplay();
  startAntiCheat();
  world.sendMessage("§a[Hardcore] System initialized");
});
