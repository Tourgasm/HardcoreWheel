/**
 * wheelScoreboards.js - Initialize and manage wheel-related scoreboards
 */

import { world } from "@minecraft/server";

export function initializeScoreboards() {
  try {
    world.scoreboard.addObjective("curses", "§c§lACTIVE PUNISHMENTS");
  } catch {}
  
  try {
    world.scoreboard.addObjective("donor_kills", "§b§lDONOR KILLS");
  } catch {}

  try {
    world.scoreboard.addObjective("spinners", "§b§lTOP SPINNERS");
  } catch {}
}

export function ensureObjective(name, display) {
  try {
    world.scoreboard.addObjective(name, display);
  } catch {}
}
