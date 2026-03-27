/**
 * REVIVAL SYSTEM - Integration with Spartan Wheel Donations
 * Listens for donation events and handles player revivals
 * 
 * NOTE: Revival cost is controlled by Python server GUI (not hardcoded here)
 */

import { world, system, ItemStack } from "@minecraft/server";
import { setLivesByName, forceLivesOneSoon } from "./livesState.js";

let playerRevivalRequests = new Map(); // Track pending revival requests
let donationListener = null;
let lastProcessedRevival = new Map(); // key -> ms timestamp (dedupe)


/*
|--------------------------------------------------------------------------
| REVIVAL REQUEST SYSTEM
|--------------------------------------------------------------------------
*/

/**
 * Request a revival for a dead player (from Python server donation)
 * @param {string} playerName - Name of player to revive
 * @param {string} donorName - Name of person who donated
 * @param {number} donationAmount - Amount in USD
 */
export function requestRevival(playerName, donorName, donationAmount) {
    // Dedupe repeated events (server can resend)
    const key = `${playerName}|${donorName}|${donationAmount}`;
    const now = Date.now();
    const last = lastProcessedRevival.get(key) || 0;
    if (now - last < 2000) {
        console.warn(`[DEBUG] Duplicate revival request ignored: ${key}`);
        return;
    }
    lastProcessedRevival.set(key, now);

    // Cost validation is done by Python server GUI, not here
    // We just queue + process safely (and ignore rapid duplicates).

    const existing = playerRevivalRequests.get(playerName);
    if (existing && (now - existing.timestamp) < 5000) {
        console.warn(`⚠️ Duplicate revival ignored for ${playerName} (within 5s)`);
        return false;
    }

    // Store revival request (used for offline players, and as a debounce guard)
    playerRevivalRequests.set(playerName, {
        donor: donorName,
        amount: donationAmount,
        timestamp: now,
    });

    console.log(`✅ Revival queued: ${playerName} (donated by ${donorName} - $${donationAmount})`);

    // Process revival on next server tick
    system.run(() => {
        processRevival(playerName, donorName, donationAmount, /*fromSpawn*/ false);
    });

    return true;
}

/**
 * Execute the actual revival
 */
function processRevival(playerName, donorName, donationAmount, fromSpawn = false) {
    const players = world.getPlayers();
    let targetPlayer = null;

    // Find the player (may be offline, so we track by name)
    for (const player of players) {
        if (player.name === playerName) {
            targetPlayer = player;
            break;
        }
    }

    // Block revival if world ended
    if (targetPlayer && targetPlayer.hasTag("world_ended")) {
        targetPlayer.sendMessage("§cCannot revive: The world has ended!");
        return;
    }

    if (targetPlayer) {

        // If this was triggered from the donation tick (not from a join/spawn hook),
        // clear the pending request now so we don't double-process on playerSpawn.
        if (!fromSpawn) {
            playerRevivalRequests.delete(playerName);
        }

        // Get player location for particles
        const playerPos = targetPlayer.location;
        const overworld = world.getDimension("overworld");
        
        // Remove hardcore_dead tag if they have it
        if (targetPlayer.hasTag("hardcore_dead")) {
            targetPlayer.removeTag("hardcore_dead");
            console.log(`🔄 ${playerName} hardcore_dead tag removed`);
        }

        // Hardcore-style revive: always restore to EXACTLY 1 life.
        try { setLivesByName(playerName, 1); } catch {}
        try { forceLivesOneSoon(targetPlayer); } catch {}        // ✨ ADD PARTICLE EFFECTS AROUND PLAYER ✨
        try {
            // Only use safe particles
            overworld.runCommand(`particle minecraft:heart ${playerPos.x} ${playerPos.y + 1} ${playerPos.z}`);
            overworld.runCommand(`particle minecraft:totem_resurrection ${playerPos.x} ${playerPos.y} ${playerPos.z}`);
        } catch (e) {
            console.warn(`Could not spawn particles: ${e}`);
        }        // Switch from spectator to survival if needed
        try {
            targetPlayer.runCommand("gamemode survival @s");
            console.log(`${playerName} switched to survival mode`);
        } catch (e) {
            console.warn(`Could not switch gamemode: ${e}`);
        }

        // Notify all players
        world.sendMessage(
            `§a✨ ${playerName} has been §lREVIVED§r§a by $${donationAmount} donation from §l${donorName}§r`
        );
        world.sendMessage(
            `§6❤ ${playerName} restored to 1 life!`
        );

        // Give starter items back (only once)
        if (!targetPlayer.hasTag("revival_kit_given")) {
            try { targetPlayer.addTag("revival_kit_given"); } catch {}
            giveStarterKit(targetPlayer);
        }
    } else {
        // Player not in world, but store for when they rejoin
        world.sendMessage(
            `§e⏳ Revival scheduled for ${playerName} by ${donorName}`
        );
    }

    // Update revival tracker (Dimension.runCommand is sync in Bedrock, so no .catch!)
    const overworld = world.getDimension("overworld");
    try {
        overworld.runCommand(`scoreboard objectives add revival_count dummy`);
    } catch {}
    try {
        // Always wrap donorName in quotes for scoreboard safety
        overworld.runCommand(`scoreboard players add "${donorName}" revival_count 1`);
    } catch {}
}

/**
 * Give starter kit to revived player
 */
function giveStarterKit(player) {
    try {
        // Restore basic items
        const items = [
            new ItemStack("minecraft:wooden_pickaxe", 1),
            new ItemStack("minecraft:wooden_axe", 1),
            new ItemStack("minecraft:wooden_shovel", 1),
            new ItemStack("minecraft:crafting_table", 1),
            new ItemStack("minecraft:chest", 1),
            new ItemStack("minecraft:bread", 32),
        ];

        for (const item of items) {
            player.getComponent("minecraft:inventory").container.addItem(item);
        }

        player.sendMessage("§a✅ Revival starter kit received!");
    } catch (err) {
        console.warn(`Could not give starter kit: ${err.message}`);
    }
}

/*
|--------------------------------------------------------------------------
| RESPAWN HOOK - CHECK FOR PENDING REVIVALS
|--------------------------------------------------------------------------
*/

world.afterEvents.playerSpawn.subscribe(event => {
    const player = event.player;

    // Check if there's a pending revival for this player
    if (playerRevivalRequests.has(player.name)) {
        const request = playerRevivalRequests.get(player.name);
        playerRevivalRequests.delete(player.name);

        system.run(() => {
            processRevival(player.name, request.donor, request.amount, /*fromSpawn*/ true);
        });
    }
});

/*
|--------------------------------------------------------------------------
| EXPORT FUNCTIONS FOR WEBSOCKET INTEGRATION
|--------------------------------------------------------------------------
*/

export function getRevivalRequests() {
    return Object.fromEntries(playerRevivalRequests);
}
