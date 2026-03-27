/**
 * wheelEventHandlers.js - Event listeners and handlers for wheel events
 */

import { world, system } from "@minecraft/server";
import { worldCmd, displayLeaderboard } from "./wheelHelpers.js";
import { killTracker, spinTracker, activeChallenges } from "./wheelConfig.js";
import { subscribeToDeaths } from "./deathEventManager.js";

export function registerDeathEventListener(applyCommandCallback) {
  subscribeToDeaths((dyingEntity) => {
    const playerName = dyingEntity.name;
    const challengeData = activeChallenges.get(playerName);
    
    world.sendMessage(`💀 [DEBUG] Player died: ${playerName}, has challenge data: ${!!challengeData}`);

    if (challengeData && Date.now() < challengeData.endTime) {
      const donorName = challengeData.donor;
      killTracker[donorName] = (killTracker[donorName] || 0) + 1;
      
      world.sendMessage(`§7[§e${challengeData.actionId}§7] §e${playerName} §7was eliminated. §e${donorName} §7now has §c${killTracker[donorName]} §7kill(s)`);
      
      try {
        worldCmd(`scoreboard players set "${donorName}" donor_kills ${killTracker[donorName]}`);
      } catch (err) {}
      
      try {
        const deathData = {
          donor: donorName,
          kills: killTracker[donorName]
        };
        world.sendMessage(`📤 [DEBUG] Sending death data to Python`);
        const encodedMessage = encodeURIComponent(JSON.stringify(deathData));
        worldCmd(`tellraw @a {"rawtext":[{"text":"__DEATH_DATA__:${encodedMessage}"}]}`);
      } catch (err) {
        world.sendMessage(`❌ [DEBUG] Error sending death message: ${err}`);
      }
      displayLeaderboard(killTracker, spinTracker);
    }

    activeChallenges.delete(playerName);
  });
}

export function registerScriptEventListener(applyCommandCallback) {
  system.afterEvents.scriptEventReceive.subscribe((ev) => {
    if (ev.id === "wheel:run") {
      let cmd;
      try {
        cmd = JSON.parse(ev.message);
      } catch {
        return;
      }
      
      // Handle leaderboard updates
      if (cmd?.type === "UPDATE_LEADERBOARD" && cmd?.killers) {
        cmd.killers.forEach((killer) => {
          killTracker[killer.name] = killer.kills;
        });
        displayLeaderboard(killTracker, spinTracker);
        return;
      }
      
      if (!cmd?.action) return;
      applyCommandCallback(cmd);
      return;
    }

    if (ev.id === "wheel:setup") {
      const [action, name] = ev.message.split(" ");

      if (action === "test_doom") {
        applyCommandCallback({
          action: "DESTROY_WORLD",
          meta: { hits: 3, required: 6, isFinal: false },
        });
        return;
      }

      if (action === "list") {
        const targets = world
          .getPlayers()
          .filter((p) => p.hasTag("wheel_target"))
          .map((p) => p.name);

        world.sendMessage(
          targets.length ? `§bVictim Pool: ${targets.join(", ")}` : "§7Pool is empty."
        );
        return;
      }

      const target = world.getPlayers().find((p) => p.name === name);
      if (!target) return;

      if (action === "add") {
        target.addTag("wheel_target");
        world.sendMessage(`§a[Wheel] Added ${name}`);
        return;
      }

      if (action === "remove") {
        target.removeTag("wheel_target");
        world.sendMessage(`§e[Wheel] Removed ${name}`);
        return;
      }
    }
  });
}
