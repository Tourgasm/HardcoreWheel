/**
 * bridge.js - Main entry point for the Spartan Wheel system
 * Imports and initializes all wheel-related modules
 */

import { world, system } from "@minecraft/server";
import { initializeScoreboards } from "./lib/wheelScoreboards.js";
import { worldCmd, getOverworld } from "./lib/wheelHelpers.js";
import { registerDeathEventListener, registerScriptEventListener } from "./lib/wheelEventHandlers.js";
import { applyCommand } from "./lib/wheelCommands.js";
import { startEnforcementSystem } from "./lib/wheelEnforcement.js";
import { initializeDeathEventManager } from "./lib/deathEventManager.js";

/* ======================================================
   INITIALIZATION
====================================================== */

function initializeWheel() {
  initializeScoreboards();

  // Set donor kills as sidebar display
  try {
    worldCmd("scoreboard objectives setdisplay sidebar donor_kills");
  } catch {}

  // Connect to Python server via MCWSS
  try {
    worldCmd("connect localhost:3001");
    world.sendMessage("§a[Wheel] Connected to Python server at localhost:3001");
  } catch (err) {
    world.sendMessage("§c[Wheel] Failed to connect: " + err.message);
  }
}

/* ======================================================
   REGISTER EVENT LISTENERS
====================================================== */

function registerEventListeners() {
  // Register death events for challenge tracking
  registerDeathEventListener(applyCommand);

  // Register script events for wheel commands
  registerScriptEventListener(applyCommand);

  // Register doom respawn handler
  world.afterEvents.playerSpawn.subscribe((event) => {
    const player = event.player;

    if (player.hasTag("doom_dead")) {
      system.run(() => {
        try {
          player.runCommand("gamemode spectator @s");
          world.sendMessage(`§c${player.name} has been locked in spectator by DOOM`);
        } catch (err) {
          world.sendMessage(`❌ Error setting spectator for ${player.name}: ${err}`);
        }
      });
    }
  });

  // Doom anti-cheat
  system.runInterval(() => {
    for (const player of world.getPlayers()) {
      if (player.hasTag("doom_dead")) {
        try {
          if (player.getGameMode() !== "spectator") {
            player.runCommand("gamemode spectator @s");
          }
        } catch (err) {
          // Silently fail if player leaves
        }
      }
    }
  }, 100);
}

/* ======================================================
   MAIN STARTUP
====================================================== */

system.run(() => {
  // Initialize the shared death event manager FIRST
  // This ensures all death events are centrally managed
  initializeDeathEventManager();
  
  initializeWheel();
  registerEventListeners();
  startEnforcementSystem();
  world.sendMessage("§a[Wheel] Spartan Wheel system initialized");
});
