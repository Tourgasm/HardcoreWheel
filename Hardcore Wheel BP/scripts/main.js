import { world, system } from "@minecraft/server";
import { requestRevival } from "./revival.js";
import { LIVES_PER_PLAYER, playerLives, ensureLives, setLivesByName, forceLivesOneSoon } from "./livesState.js";

const DIFFICULTY_PHASE = 5;
// Default world-end threshold (can be overridden live by the Wheel Server)
let worldEndPhase = 20;
let hardcoreModeEnabled = true;  // Toggle for hardcore world (world end + lives)
const LOCK_TAG = "hardcore_locked";

let worldEnded = false;
let totalDeaths = 0;
const lastRevivalEventAt = new Map(); // playerName -> ms timestamp (dedupe repeated revival events)

function setLives(player, lives) {
    return setLivesByName(player.name, lives);
}



/*
|--------------------------------------------------------------------------
| SCRIPT EVENT LISTENER (for Python server commands)
|--------------------------------------------------------------------------
*/

system.afterEvents.scriptEventReceive.subscribe(event => {
    console.warn("[DEBUG] Script event received:", event.id, event.sourceType, event.message);
    // Only listen to wheel:run events from the Python server
    if (event.id !== "wheel:run") return;
    if (event.sourceType !== "Server" && event.sourceType !== "External" && event.sourceType !== "Entity") return;
    
    try {
        const data = JSON.parse(event.message);
        console.warn("[DEBUG] Parsed event data:", JSON.stringify(data));
        // Handle config updates from the Wheel Server
        if (data.type === "config" && data.action === "SET_WORLD_END_DEATHS") {
            const raw = Number(data.value);
            const clamped = Math.max(20, Math.min(150, Math.floor(isFinite(raw) ? raw : 20)));
            worldEndPhase = clamped;
            console.warn(`[DEBUG] World end threshold updated: ${worldEndPhase} deaths`);
            return;
        }

        // Handle hardcore mode toggle from the Wheel Server
        if (data.type === "config" && data.action === "SET_HARDCORE_MODE") {
            hardcoreModeEnabled = Boolean(data.value);
            console.warn(`[DEBUG] Hardcore mode: ${hardcoreModeEnabled ? "ON" : "OFF"}`);
            return;
        }

        // Handle revival command from Python server
        if (data.type === "revival" && data.action === "REVIVAL") {
            const playerName = data.player || "@a";
            // Dedupe: the server may send the same revival event multiple times
            const now = Date.now();
            const last = lastRevivalEventAt.get(playerName) || 0;
            if (now - last < 2000) {
                console.warn(`[DEBUG] Duplicate revival ignored for ${playerName}`);
                return;
            }
            lastRevivalEventAt.set(playerName, now);
            const donorName = data.donor || "Anonymous";
            const amount = data.amount || 0;
            console.warn("[DEBUG] Calling requestRevival with:", playerName, donorName, amount);
            requestRevival(playerName, donorName, amount);
            // If the player is currently online, force lives to exactly 1 (now + next tick + 1s)
            const online = world.getPlayers().find(p => p.name === playerName);
            if (online) {
                forceLivesOneSoon(online);
            }


        }
    } catch (e) {
        console.warn(`[Script Event] Error parsing message: ${e}`);
    }
});

/*
|--------------------------------------------------------------------------
| SAFE INIT
|--------------------------------------------------------------------------
*/

system.run(() => {
    const overworld = world.getDimension("overworld");

    // Disable command feedback (prevents spam)
    overworld.runCommand("gamerule sendcommandfeedback false");
    overworld.runCommand("gamerule commandblockoutput false");

    // Initialize all players with 3 lives
    for (const player of world.getPlayers()) {
        ensureLives(player.name);
    }

    world.sendMessage("☠️ Hardcore World Initialized");
});

/*
|--------------------------------------------------------------------------
| DEATH HANDLING
|--------------------------------------------------------------------------
*/

world.afterEvents.entityDie.subscribe(event => {
    if (worldEnded) {
        event.deadEntity?.addTag?.("hardcore_dead");
        return;
    }
    const dead = event.deadEntity;
    if (dead.typeId !== "minecraft:player") return;

    // Skip hardcore logic if hardcore mode is disabled
    if (!hardcoreModeEnabled) {
        return;
    }

    // Initialize lives if not set
    ensureLives(dead.name);

    // Decrement lives and clamp to 0
    let lives = playerLives.get(dead.name);
    lives = Math.max(0, lives - 1);
    playerLives.set(dead.name, lives);
    totalDeaths++;

    // Show message with total deaths and remaining lives
    if (lives > 0) {
        world.sendMessage(`§c☠ ${dead.name} has fallen (${totalDeaths}) §6Lives remaining: ${lives}`);
    } else {
        world.sendMessage(`§4☠ ${dead.name} is permanently dead! §7Total deaths: (${totalDeaths})`);
        dead.addTag("hardcore_dead");
    }

    if (totalDeaths === DIFFICULTY_PHASE) escalateDifficulty();
    if (totalDeaths === worldEndPhase) endWorld();
});

/*
|-------------------------------------------------------------------------
| UPON RESPAWN (Auto-Kick Trigger)
|-------------------------------------------------------------------------
*/
world.afterEvents.playerSpawn.subscribe(event => {
    const player = event.player;

    // Initialize lives on first join
    ensureLives(player.name);

    // If a revival just happened, don't ever "default" them back up.
    if (player.hasTag("revived_recently")) {
        setLives(player, 1);
    }

    // ✨ CHECK FOR REVIVAL - RESTORE 1 LIFE ✨
    if (player.hasTag("world_ended")) {
        // Block revival/respawn if world ended
        try {
            player.runCommand("gamemode spectator @s");
        } catch {}
        return;
    }
    if (player.hasTag("revival_restore_lives")) {
        player.removeTag("revival_restore_lives");
        // Remove hardcore_dead if present
        if (player.hasTag("hardcore_dead")) {
            player.removeTag("hardcore_dead");
        }
        // Set gamemode to survival (in case they were spectator)
        try {
            player.runCommand("gamemode survival @s");
        } catch (e) {
            // Ignore errors (e.g., if already in survival)
        }
        // Always restore to exactly 1 life on revival
        forceLivesOneSoon(player);
        world.sendMessage(`§a✨ ${player.name} has been revived! Lives: 1/${LIVES_PER_PLAYER}`);
        return; // Don't kick them - they're revived!
    }

    if (player.hasTag("hardcore_dead") || worldEnded) {
        // Delay by one tick to prevent engine crashes during respawn
        system.run(() => {
            try {
                player.kick("§cHARDCORE: Death is permanent. This world is lost to you.");
            } catch (e) {
                // If the player is the Host, they cannot be kicked. Set to spectator instead.
                player.runCommand("gamemode spectator @s");
            }
        });
    }
});

/*
|--------------------------------------------------------------------------
| ACTIONBAR DISPLAY (Lives Counter)
|--------------------------------------------------------------------------
*/

system.runInterval(() => {
    for (const player of world.getPlayers()) {
        if (!player.hasTag("hardcore_dead") && !worldEnded) {
            // Clamp lives to minimum 0 to avoid RangeError
            const lives = Math.max(0, playerLives.get(player.name) ?? LIVES_PER_PLAYER);
            const hearts = "❤".repeat(lives);
            player.onScreenDisplay.setActionBar(`§c${hearts} §7Lives: §6${lives}`);
        }
    }
}, 10); // Update every 0.5 seconds

/*
|--------------------------------------------------------------------------
| ANTI-CHEAT & REJOIN PROTECTION
|--------------------------------------------------------------------------
*/

system.runInterval(() => {
    for (const player of world.getPlayers()) {
        if (player.hasTag("hardcore_dead")) {
            try {
                player.kick("§cHARDCORE: You are currently dead.");
            } catch (e) {
                // Safety fallback for Host
                if (player.getGameMode() !== "spectator") {
                    player.runCommand(`gamemode spectator "${player.name}"`);
                }
            }
        }
    }
}, 100); // Check every 5 seconds

/*
|--------------------------------------------------------------------------
| PHASE ACTIONS
|--------------------------------------------------------------------------
*/

function escalateDifficulty() {
    const overworld = world.getDimension("overworld");
    world.sendMessage("⚠️ The world grows hostile...");
    overworld.runCommand("difficulty hard");
    overworld.runCommand("weather thunder 1200");
}

function endWorld() {
    if (worldEnded) return;
    worldEnded = true;

    const overworld = world.getDimension("overworld");
    world.sendMessage("§4☠ THE WORLD IS LOST ☠");

    for (const player of world.getPlayers()) {
        if (!player.hasTag("hardcore_dead")) {
            player.addTag("hardcore_dead");
            player.runCommand("kill @s");
        }
        // Add world_ended tag to all players
        player.addTag("world_ended");
        // Set to spectator
        try {
            player.runCommand("gamemode spectator @s");
        } catch {}
    }

    for (let i = 0; i < 5; i++) {
        overworld.runCommand("summon minecraft:wither ~ ~5 ~");
    }

    // Send wheel:pause event to Python server
    try {
        overworld.runCommand('scriptevent wheel:pause {"reason":"world_end"}');

        // Also send a chat signal for external tools listening via PlayerMessage (MCWSS)
        try {
            const pausePayload = { type: "wheel:pause", reason: "world_end" };
            const encodedPause = encodeURIComponent(JSON.stringify(pausePayload));
            overworld.runCommand(`tellraw @a {"rawtext":[{"text":"__WHEEL_PAUSE__:${encodedPause}"}]}`);
        } catch {}

    } catch {}
}