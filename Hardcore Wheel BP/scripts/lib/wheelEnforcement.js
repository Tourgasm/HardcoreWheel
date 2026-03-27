/**
 * wheelEnforcement.js - Tick-based enforcement system for active curse effects
 */

import { world, system } from "@minecraft/server";
import { safeCmd, getBlockBelow } from "./wheelHelpers.js";
import { DEFAULTS, LOOP_TICKS } from "./wheelConfig.js";

export function startEnforcementSystem() {
  system.runInterval(() => {
    for (const p of world.getPlayers()) {
      enforceNoEating(p);
      enforceDimensionalChaos(p);
      enforceOneBlockMode(p);
      enforceNoShelter(p);
      enforceLavaFloor(p);
    }
  }, LOOP_TICKS);
}

function enforceNoEating(player) {
  if (player.hasTag("no_eat")) {
    [
      "apple", "bread", "carrot", "cooked_beef", "cooked_chicken",
      "golden_apple", "enchanted_golden_apple", "rotten_flesh", "porkchop",
      "chicken", "beef", "cooked_cod", "cooked_salmon", "cod", "salmon",
    ].forEach((f) => safeCmd(player, `clear @s ${f}`));
  }
}

function enforceDimensionalChaos(player) {
  if (player.hasTag("dimensional_chaos")) {
    let timeLeft = player.getDynamicProperty("chaos_time_left") ?? 0;
    let nextTp = player.getDynamicProperty("chaos_next_tp") ?? 0;

    if (timeLeft <= 0) {
      player.removeTag("dimensional_chaos");
      player.setDynamicProperty("chaos_time_left", 0);
      player.setDynamicProperty("chaos_next_tp", 0);
      return;
    }

    player.setDynamicProperty("chaos_time_left", timeLeft - 1);

    if (nextTp <= 0) {
      const dimensions = ["overworld", "nether", "the_end"];
      const randomDim = dimensions[Math.floor(Math.random() * dimensions.length)];
      
      safeCmd(player, `execute in ${randomDim} run tp @s ~ 100 ~`);
      safeCmd(player, `effect @s slow_falling 10 0 true`);
      
      player.onScreenDisplay.setActionBar(`§5§lDIMENSIONAL CHAOS! §f${timeLeft}s`);
      player.setDynamicProperty("chaos_next_tp", 10);
    } else {
      player.setDynamicProperty("chaos_next_tp", nextTp - 1);
    }
  }
}

function enforceOneBlockMode(player) {
  const lockTag = player.getTags().find((t) => t.startsWith("blocklock_"));
  if (lockTag) {
    const allowed = lockTag.replace("blocklock_", "");
    const blockBelow = getBlockBelow(player);

    if (blockBelow && !blockBelow.isAir && !blockBelow.isLiquid) {
      const current = blockBelow.typeId.replace("minecraft:", "");

      if (current !== allowed) {
        player.onScreenDisplay.setActionBar(`§c§lONLY STAND ON ${allowed.toUpperCase()}`);
        safeCmd(player, "damage @s 2");
      }
    }
  }
}

function enforceNoShelter(player) {
  if (player.hasTag("no_shelter")) {
    const dim = player.dimension.id;
    const time = world.getTimeOfDay();
    const isNight = time >= 13000 && time <= 23000;

    const isDangerous =
      dim === "minecraft:the_nether" ||
      dim === "minecraft:the_end" ||
      (dim === "minecraft:overworld" && isNight);

    if (dim === "minecraft:overworld" && !isNight) {
      player.onScreenDisplay.setActionBar("§a☀ Daytime — Shelter allowed");
      player.setDynamicProperty("shelter_grace", 0);
    } else if (isDangerous) {
      const ray = player.dimension.getBlockFromRay(
        { x: player.location.x, y: player.location.y + 2, z: player.location.z },
        { x: 0, y: 1, z: 0 },
        { maxDistance: 40 }
      );

      const isSheltered =
        ray && ray.block && !ray.block.isAir && !ray.block.typeId.includes("leaves");

      if (isSheltered) {
        let grace = player.getDynamicProperty("shelter_grace") ?? 0;
        grace++;
        player.setDynamicProperty("shelter_grace", grace);

        const secondsLeft = Math.max(0, DEFAULTS.shelterPunishAfter - grace);
        player.onScreenDisplay.setActionBar(
          `§c§lNO SHELTER! LEAVE COVER (${secondsLeft}s)`
        );

        if (grace >= DEFAULTS.shelterPunishAfter) {
          if (dim === "minecraft:overworld") {
            safeCmd(player, "tp @s ~ 200 ~");
            safeCmd(player, "effect @s slow_falling 30 0 true");
          } else if (dim === "minecraft:the_nether") {
            safeCmd(player, "effect @s fire 3 0 true");
            safeCmd(player, "damage @s 2");
          } else if (dim === "minecraft:the_end") {
            safeCmd(player, "effect @s levitation 5 10 true");
            player.onScreenDisplay.setActionBar("§d§lTHE VOID PULLS YOU UP!");
          }

          player.setDynamicProperty("shelter_grace", 0);
        }
      } else {
        player.setDynamicProperty("shelter_grace", 0);
      }
    }
  }
}

function enforceLavaFloor(player) {
  if (player.hasTag("lava_floor")) {
    let timeLeft = player.getDynamicProperty("lava_time_left") ?? 0;

    if (timeLeft <= 0) {
      player.removeTag("lava_floor");
      player.setDynamicProperty("lava_tick", 0);
      player.setDynamicProperty("lava_time_left", 0);
      player.setDynamicProperty("lava_last_x", 0);
      player.setDynamicProperty("lava_last_y", 0);
      player.setDynamicProperty("lava_last_z", 0);
      player.onScreenDisplay.setActionBar("");
      return;
    }

    player.setDynamicProperty("lava_time_left", timeLeft - 1);

    const blockBelow = player.dimension.getBlock({
      x: Math.floor(player.location.x),
      y: Math.floor(player.location.y - 1),
      z: Math.floor(player.location.z),
    });

    if (!blockBelow || blockBelow.isAir || blockBelow.isLiquid) {
      player.setDynamicProperty("lava_tick", 0);
      player.setDynamicProperty("lava_last_x", player.location.x);
      player.setDynamicProperty("lava_last_y", player.location.y);
      player.setDynamicProperty("lava_last_z", player.location.z);
      return;
    }

    const lastX = player.getDynamicProperty("lava_last_x") ?? player.location.x;
    const lastY = player.getDynamicProperty("lava_last_y") ?? player.location.y;
    const lastZ = player.getDynamicProperty("lava_last_z") ?? player.location.z;
    
    const isStationary = 
      Math.abs(player.location.x - lastX) < 0.1 &&
      Math.abs(player.location.y - lastY) < 0.1 &&
      Math.abs(player.location.z - lastZ) < 0.1;

    let lavaTick = player.getDynamicProperty("lava_tick") ?? 0;
    if (isStationary) {
      lavaTick++;
    } else {
      lavaTick = 0;
    }
    player.setDynamicProperty("lava_tick", lavaTick);

    player.onScreenDisplay.setActionBar(
      `§c§lTHE FLOOR IS LAVA! §f${timeLeft}s`
    );

    if (lavaTick >= 2) {
      player.runCommandAsync("damage @s 2");
      player.setDynamicProperty("lava_tick", 0);
    }

    player.setDynamicProperty("lava_last_x", player.location.x);
    player.setDynamicProperty("lava_last_y", player.location.y);
    player.setDynamicProperty("lava_last_z", player.location.z);
  }
}
