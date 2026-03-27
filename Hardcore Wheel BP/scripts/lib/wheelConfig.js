/**
 * wheelConfig.js - Configuration for the Spartan Wheel system
 * Centralized config for all wheel-related constants
 */

export const LOOP_TICKS = 20; // Run enforcement every 1 second (20 ticks)

export const DEFAULTS = {
  oneBlockSeconds: 60,
  noShelterSeconds: 1200, // 20 minutes
  noEatSeconds: 300,      // 5 minutes
  lavaSeconds: 30,        // lava mode duration
  shelterPunishAfter: 5,  // seconds under cover before punishment
  lavaDamageEvery: 2      // seconds standing on blocks before damage tick
};

export const DEADLY_CHALLENGES = [
  "MLG_CHALLENGE",
  "ZOMBIE_HORDE",
  "CREEPER_SQUAD",
  "PHANTOM_ATTACK",
  "FLOOR_IS_LAVA",
  "TNT_RAIN",
  "JAILBREAK"
];

// Track kill counts and active challenges
export const killTracker = {};          // { donorName: killCount }
export const spinTracker = {};          // { donorName: spinCount }
export const activeChallenges = new Map(); // Map<playerName, { donor, endTime, actionId }>
