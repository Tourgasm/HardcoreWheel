/**
 * deathEventManager.js - Centralized death event handling
 * Ensures all player deaths (natural, wheel challenges, etc.) are tracked
 * by both the hardcore system and wheel leaderboard system
 */

import { world } from "@minecraft/server";

// Subscribers to death events
const deathSubscribers = [];

/**
 * Register a callback to be called whenever a player dies
 * @param {Function} callback - Function called with (deadPlayer, event)
 */
export function subscribeToDeaths(callback) {
  deathSubscribers.push(callback);
}

/**
 * Initialize the death event manager
 * This should only be called once at startup
 */
export function initializeDeathEventManager() {
  world.afterEvents.entityDie.subscribe((event) => {
    const deadEntity = event.deadEntity;
    
    // Only track player deaths
    if (deadEntity.typeId !== "minecraft:player") return;

    // Notify all subscribers
    for (const subscriber of deathSubscribers) {
      try {
        subscriber(deadEntity, event);
      } catch (err) {
        console.warn(`[DeathEventManager] Error in subscriber: ${err}`);
      }
    }
  });
}
