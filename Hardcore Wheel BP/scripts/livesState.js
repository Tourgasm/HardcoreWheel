import { system } from "@minecraft/server";

// Single source of truth for lives across modules.
export const LIVES_PER_PLAYER = 5;

// Map: playerName -> lives
export const playerLives = new Map();

export function clampLives(v) {
  return Math.max(0, Math.min(LIVES_PER_PLAYER, v));
}

export function getLivesByName(playerName) {
  return playerLives.get(playerName);
}

export function ensureLives(playerName) {
  if (!playerLives.has(playerName)) {
    playerLives.set(playerName, LIVES_PER_PLAYER);
  }
  return playerLives.get(playerName);
}

export function setLivesByName(playerName, lives) {
  const v = clampLives(lives);
  playerLives.set(playerName, v);
  return v;
}

// Helps stomp race conditions during revive/respawn.
export function forceLivesOneSoon(playerNameOrPlayer) {
  const name = (typeof playerNameOrPlayer === "string")
    ? playerNameOrPlayer
    : (playerNameOrPlayer?.name || "");

  if (!name) return;

  try { setLivesByName(name, 1); } catch {}
  try { system.run(() => { try { setLivesByName(name, 1); } catch {} }); } catch {}
  try { system.runTimeout(() => { try { setLivesByName(name, 1); } catch {} }, 20); } catch {}
}
