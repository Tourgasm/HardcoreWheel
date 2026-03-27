/**
 * wheelHelpers.js - Utility functions for the wheel system
 */

import { world, system } from "@minecraft/server";

export function getOverworld() {
  return world.getDimension("overworld");
}

export function worldCmd(command) {
  try {
    return getOverworld().runCommandAsync(command);
  } catch (err) {
    // silently swallow errors
  }
}

export function safeCmd(player, command) {
  try {
    player.runCommandAsync(command);
  } catch {}
}

export function getBlockBelow(player) {
  return player.dimension.getBlock({
    x: Math.floor(player.location.x),
    y: Math.floor(player.location.y - 1),
    z: Math.floor(player.location.z),
  });
}

export function clearAllBlockLocks(player) {
  for (const t of player.getTags()) {
    if (t.startsWith("blocklock_")) player.removeTag(t);
  }
}

export function setTimedTag(player, tag, seconds, onEnd) {
  player.addTag(tag);
  if (typeof seconds === "number" && seconds > 0) {
    system.runTimeout(() => {
      player.removeTag(tag);
      if (onEnd) onEnd();
    }, seconds * 20); // convert seconds to ticks for timeout
  }
}

export function displayLeaderboard(killTracker, spinTracker) {
  // Combine and sort by kills
  const leaderboard = Object.keys(killTracker).map(name => ({
    name,
    kills: killTracker[name],
    spins: spinTracker[name] || 0
  })).sort((a, b) => b.kills - a.kills).slice(0, 3);

  if (leaderboard.length === 0) return;

  let message = `\n§b━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n§b  DONOR LEADERBOARD\n§b━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
  
  leaderboard.forEach((donor, index) => {
    const medal = index === 0 ? "🥇" : index === 1 ? "🥈" : "🥉";
    message += `§e  ${medal} ${donor.name}§r       ${donor.spins} Spins  |  §c${donor.kills} Kills\n`;
  });

  message += `§b━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
  world.sendMessage(message);
}
