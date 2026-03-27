/**
 * wheelCommands.js - Command processing and execution
 */

import { world, system } from "@minecraft/server";
import { safeCmd, getBlockBelow, clearAllBlockLocks, worldCmd, displayLeaderboard } from "./wheelHelpers.js";
import { DEFAULTS, killTracker, spinTracker, activeChallenges } from "./wheelConfig.js";

export function applyCommand(cmd) {
  const displayAction = String(cmd.action).replace(/_/g, " ");
  const donorName = cmd.player || "Someone";
  world.sendMessage(`§e${donorName.toUpperCase()} §7spun the wheel. §l§c🎯 THE WHEEL HAS CHOSEN: §f${displayAction}`);
  
  // Update top spinners scoreboard
  if (cmd.meta?.topSpinners && Array.isArray(cmd.meta.topSpinners)) {
    try {
      cmd.meta.topSpinners.forEach((spinner, index) => {
        const scoreValue = spinner.count;
        worldCmd(`scoreboard players set "${spinner.name}" spinners ${scoreValue}`);
        spinTracker[spinner.name] = spinner.count;
      });
    } catch (err) {}
  }

  // Track this spin for the donor
  spinTracker[donorName] = (spinTracker[donorName] || 0) + 1;

  for (const player of world.getPlayers()) {
    const inventory = player.getComponent("minecraft:inventory")?.container;

    // Full screen splash
    safeCmd(player, `title @s title §c§l${displayAction}`);
    safeCmd(player, `title @s subtitle §fHold on tight!`);

    executeWheelAction(cmd, player, donorName, inventory);
  }
}

function executeWheelAction(cmd, player, donorName, inventory) {
  switch (cmd.action) {
    case "TNT_RAIN": {
      activeChallenges.set(player.name, { donor: donorName, endTime: Date.now() + 30000, actionId: cmd.action });
      
      for (let i = 0; i < 8; i++) {
        const x = (Math.random() - 0.5) * 10;
        const z = (Math.random() - 0.5) * 10;
        safeCmd(player, `execute at @s run summon tnt ~${x} ~12 ~${z}`);
      }
      break;
    }

    case "CLEANSE": {
      player.removeTag("no_eat");
      player.removeTag("no_shelter");
      player.removeTag("lava_floor");
      player.setDynamicProperty("lava_tick", 0);
      player.setDynamicProperty("shelter_grace", 0);
      clearAllBlockLocks(player);
      safeCmd(player, "effect @s clear");
      try {
        safeCmd(player, "scoreboard players reset @s curses");
      } catch {}
      break;
    }

    case "FLOOR_IS_LAVA": {
      const durationSeconds =
        Number.isFinite(Number(cmd.meta?.durationSeconds))
          ? Number(cmd.meta.durationSeconds)
          : 60;

      player.addTag("lava_floor");
      player.setDynamicProperty("lava_tick", 0);
      player.setDynamicProperty("lava_time_left", durationSeconds);
      const initPos = player.location;
      player.setDynamicProperty("lava_last_x", initPos.x);
      player.setDynamicProperty("lava_last_y", initPos.y);
      player.setDynamicProperty("lava_last_z", initPos.z);

      player.onScreenDisplay.setActionBar(
        `§c§lTHE FLOOR IS LAVA! §f${durationSeconds}s`
      );

      activeChallenges.set(player.name, { donor: donorName, endTime: Date.now() + durationSeconds * 1000, actionId: cmd.action });
      system.runTimeout(() => activeChallenges.delete(player.name), durationSeconds * 20);
      break;
    }

    case "NO_ATTACK": {
      safeCmd(player, "gamemode adventure @s");
      system.runTimeout(() => safeCmd(player, "gamemode survival @s"), 60 * 20);
      break;
    }

    case "LOSE_HOTBAR": {
      if (!inventory) break;

      const raw = cmd.meta?.slot;
      const slot = raw === "ALL" ? "ALL" : Number.isFinite(Number(raw)) ? Number(raw) : undefined;

      for (let i = 0; i < 9; i++) {
        if (slot !== "ALL" && i !== slot - 1) continue;
        inventory.setItem(i, undefined);
      }

      if (slot === "ALL") {
        player.onScreenDisplay.setActionBar("§c§lALL HOTBAR SLOTS DESTROYED");
      } else if (typeof slot === "number") {
        player.onScreenDisplay.setActionBar(`§c§lHOTBAR SLOT ${slot} DESTROYED`);
      } else {
        player.onScreenDisplay.setActionBar("§c§lHOTBAR HIT!");
      }
      break;
    }

    case "LOSE_INVENTORY": {
      if (!inventory) break;
      for (let i = 0; i < inventory.size; i++) {
        inventory.setItem(i, undefined);
      }
      break;
    }

    case "NO_TOOLS": {
      const mats = ["wooden", "stone", "iron", "golden", "diamond", "netherite"];
      const toolTypes = ["pickaxe", "axe", "shovel", "hoe", "sword"];
      mats.forEach((m) =>
        toolTypes.forEach((t) => safeCmd(player, `clear @s ${m}_${t}`))
      );
      break;
    }

    case "WOODEN_TOOLS": {
      if (player.hasTag("wooden_tools_active")) break;
      
      player.addTag("wooden_tools_active");
      
      const tiers = ["stone", "iron", "golden", "diamond", "netherite", "wooden"];
      const types = ["pickaxe", "axe", "shovel", "hoe", "sword"];

      tiers.forEach((tr) => types.forEach((ty) => safeCmd(player, `clear @s ${tr}_${ty}`)));
      ["pickaxe", "axe", "shovel", "hoe"].forEach((t) => safeCmd(player, `give @s wooden_${t}`));

      system.runTimeout(() => {
        player.removeTag("wooden_tools_active");
      }, 300 * 20);
      break;
    }

    case "NO_ARMOR": {
      const eq = player.getComponent("minecraft:equippable");
      if (eq) ["Head", "Chest", "Legs", "Feet"].forEach((s) => eq.setEquipment(s, undefined));
      break;
    }

    case "ONE_BLOCK_MODE": {
      const blockBelow = getBlockBelow(player);

      if (!blockBelow || blockBelow.isAir || blockBelow.isLiquid) {
        player.onScreenDisplay.setActionBar("§7⚠ Cannot start One Block Mode here");
        break;
      }

      const blockId = blockBelow.typeId.replace("minecraft:", "");
      clearAllBlockLocks(player);
      player.addTag(`blocklock_${blockId}`);
      player.onScreenDisplay.setActionBar(`§b§lONE BLOCK MODE: §f${blockId.toUpperCase()}`);

      const seconds =
        Number.isFinite(Number(cmd.meta?.durationSeconds))
          ? Number(cmd.meta.durationSeconds)
          : DEFAULTS.oneBlockSeconds;

      system.runTimeout(() => {
        player.removeTag(`blocklock_${blockId}`);
      }, seconds * 20);
      break;
    }

    case "NO_SHELTER": {
      player.addTag("no_shelter");
      player.setDynamicProperty("shelter_grace", 0);

      const seconds =
        Number.isFinite(Number(cmd.meta?.durationSeconds))
          ? Number(cmd.meta.durationSeconds)
          : DEFAULTS.noShelterSeconds;

      system.runTimeout(() => {
        player.removeTag("no_shelter");
        player.setDynamicProperty("shelter_grace", 0);
      }, seconds * 20);
      break;
    }

    case "NO_EATING": {
      player.addTag("no_eat");

      const durSeconds =
        Number.isFinite(Number(cmd.meta?.durationSeconds))
          ? Number(cmd.meta.durationSeconds)
          : Number.isFinite(Number(cmd.meta?.duration))
          ? Math.max(1, Math.floor(Number(cmd.meta.duration) / 20))
          : DEFAULTS.noEatSeconds;

      safeCmd(player, `effect @s hunger ${durSeconds} 1 true`);

      system.runTimeout(() => {
        player.removeTag("no_eat");
        safeCmd(player, "effect @s clear hunger");
      }, durSeconds * 20);
      break;
    }

    case "MLG_CHALLENGE": {
      safeCmd(player, "give @s water_bucket");
      safeCmd(player, "tp @s ~ 300 ~");
      const duration = 90;
      activeChallenges.set(player.name, { donor: donorName, endTime: Date.now() + duration * 1000, actionId: cmd.action });
      system.runTimeout(() => activeChallenges.delete(player.name), duration * 20);
      break;
    }

    case "CREEPER_SQUAD": {
      for (let i = 0; i < 4; i++) safeCmd(player, "execute at @s run summon creeper ^ ^ ^-3");
      const duration = 60;
      activeChallenges.set(player.name, { donor: donorName, endTime: Date.now() + duration * 1000, actionId: cmd.action });
      system.runTimeout(() => activeChallenges.delete(player.name), duration * 20);
      break;
    }

    case "ZOMBIE_HORDE": {
      for (let i = 0; i < 5; i++) safeCmd(player, "execute at @s run summon zombie ^ ^ ^-3");
      const duration = 60;
      activeChallenges.set(player.name, { donor: donorName, endTime: Date.now() + duration * 1000, actionId: cmd.action });
      system.runTimeout(() => activeChallenges.delete(player.name), duration * 20);
      break;
    }

    case "WILD_TP": {
      safeCmd(player, "spreadplayers ~ ~ 50 100 @s");
      break;
    }

    case "COBWEB_TRAP": {
      safeCmd(player, "setblock ~ ~ ~ web");
      safeCmd(player, "setblock ~ ~1 ~ web");
      break;
    }

    case "PHANTOM_ATTACK": {
      for (let i = 0; i < 3; i++) safeCmd(player, "execute at @s run summon phantom ~ ~10 ~");
      const duration = 60;
      activeChallenges.set(player.name, { donor: donorName, endTime: Date.now() + duration * 1000, actionId: cmd.action });
      system.runTimeout(() => activeChallenges.delete(player.name), duration * 20);
      break;
    }

    case "RANDOM_STATUS": {
      const fx = ["blindness", "nausea", "slowness"];
      safeCmd(player, `effect @s ${fx[Math.floor(Math.random() * fx.length)]} 15 1 true`);
      break;
    }

    case "FOOD_SCRAMBLE": {
      [
        "apple", "bread", "carrot", "cooked_beef", "cooked_chicken",
        "golden_apple", "enchanted_golden_apple", "rotten_flesh", "porkchop",
        "chicken", "beef", "cooked_cod", "cooked_salmon", "cod", "salmon",
      ].forEach((f) => safeCmd(player, `clear @s ${f}`));

      safeCmd(player, "give @s rotten_flesh 16");
      break;
    }

    case "DESTROY_WORLD": {
      const doomHits = cmd.meta?.doomHits || 0;
      const doomRequired = cmd.meta?.doomRequired || 6;
      const doomDisplay = `§c§lDOOM: ${doomHits}/${doomRequired}`;
      const isFinal = cmd.meta?.isFinal;
      
      world.sendMessage(`[DEBUG] DESTROY_WORLD case triggered. isFinal=${isFinal}, doomHits=${doomHits}/${doomRequired}`);
      
      if (isFinal) {
        world.sendMessage(`🔥🔥🔥 DOOM ACTIVATED! Putting everyone in spectator!`);
        safeCmd(player, `tellraw @a {"rawtext":[{"text":"${doomDisplay} - WORLD DESTROYED!"}]}`);
        safeCmd(player, "kill @a");
        safeCmd(player, "tag @a add doom_dead");
        // Add world_ended tag to all players and set to spectator
        for (const p of world.getPlayers()) {
          safeCmd(p, "tag @s add world_ended");
          try { safeCmd(p, "gamemode spectator @s"); } catch {}
        }
        // Send wheel pause signal to Python server (via chat parse)
        safeCmd(player, `tellraw @a {"rawtext":[{"text":"__WHEEL_PAUSE__:{\\\"reason\\\":\\\"doom\\\"}"}]}`);
        // (Optional) also fire a scriptevent for local debugging
        try {
          worldCmd('scriptevent wheel:pause {"reason":"doom"}');
        } catch {}
      } else {
        safeCmd(player, "camerashake add @s 0.2 2 rotational");
        player.onScreenDisplay.setActionBar(doomDisplay);
      }
      break;
    }

    case "FREE_ARMOR": {
      const armorTier = cmd.meta?.armorTier || "diamond";
      const armorPiece = cmd.meta?.armorPiece || "full_set";
      const enchant = cmd.meta?.enchantment || { id: "protection", lvl: 1 };
      
      const tierToMaterial = {
        "leather": "leather", "copper": "copper", "chain": "chainmail",
        "iron": "iron", "diamond": "diamond", "netherite": "netherite"
      };
      
      const material = tierToMaterial[armorTier] || "diamond";
      
      const armorItems = {
        "helmet": [`${material}_helmet`],
        "chestplate": [`${material}_chestplate`],
        "leggings": [`${material}_leggings`],
        "boots": [`${material}_boots`],
        "full_set": [
          `${material}_helmet`,
          `${material}_chestplate`,
          `${material}_leggings`,
          `${material}_boots`
        ]
      };
      
      const itemsToGive = armorItems[armorPiece] || armorItems["full_set"];
      const enchantId = enchant.id || "protection";
      const enchantLvl = Math.max(1, Math.min(3, enchant.lvl || 1));
      const protectionCap = enchantId === "protection" ? Math.min(4, enchantLvl) : enchantLvl;
      
      itemsToGive.forEach(item => {
        safeCmd(player, `give @s ${item}`);
        safeCmd(player, `enchant @s ${enchantId} ${protectionCap}`);
      });
      
      const tierDisplay = armorTier.charAt(0).toUpperCase() + armorTier.slice(1);
      const pieceDisplay = armorPiece.replace(/_/g, " ").toUpperCase();
      const enchantDisplay = enchantId.charAt(0).toUpperCase() + enchantId.slice(1) + " " + protectionCap;
      
      player.onScreenDisplay.setActionBar(
        `§a§l🎁 ${tierDisplay.toUpperCase()} ${pieceDisplay} §f[${enchantDisplay}]`
      );
      break;
    }

    case "DIMENSIONAL_CHAOS": {
      const durationSeconds =
        Number.isFinite(Number(cmd.meta?.durationSeconds))
          ? Number(cmd.meta.durationSeconds)
          : 120;
      
      player.addTag("dimensional_chaos");
      player.setDynamicProperty("chaos_time_left", durationSeconds);
      player.setDynamicProperty("chaos_next_tp", 0);
      
      player.onScreenDisplay.setActionBar(`§5§lDIMENSIONAL CHAOS! §f${durationSeconds}s`);
      
      system.runTimeout(() => {
        player.removeTag("dimensional_chaos");
        player.setDynamicProperty("chaos_time_left", 0);
        player.setDynamicProperty("chaos_next_tp", 0);
      }, durationSeconds * 20);
      break;
    }

    case "JAILBREAK": {
      for (let i = 0; i < 2; i++) safeCmd(player, "execute at @s run summon warden ^ ^ ^-3");
      const duration = 60;
      activeChallenges.set(player.name, { donor: donorName, endTime: Date.now() + duration * 1000, actionId: cmd.action });
      system.runTimeout(() => activeChallenges.delete(player.name), duration * 20);
      break;
    }
  }
}
