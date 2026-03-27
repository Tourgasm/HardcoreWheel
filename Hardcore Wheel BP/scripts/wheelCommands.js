import { world } from "@minecraft/server";

// Using the most recent stable event name
world.beforeEvents.chatSend.subscribe((ev) => {
    const msg = ev.message.trim();
    if (!msg.startsWith("/wheel")) return;

    ev.cancel = true; // Prevents the message from appearing in chat

    const args = msg.split(" ");
    const action = args[1];
    const name = args[2];

    const sender = ev.sender;

    if (action === "add" && name) {
        const p = world.getPlayers().find(pl => pl.name === name);
        if (!p) {
            sender.sendMessage("§cPlayer not found.");
            return;
        }
        p.addTag("wheel_target");
        sender.sendMessage(`§aAdded ${name} to wheel targets.`);
    } else if (action === "list") {
        const targets = world.getPlayers().filter(p => p.hasTag("wheel_target")).map(p => p.name);
        sender.sendMessage(targets.length ? `§bTargets: ${targets.join(", ")}` : "§7No targets.");
    } else {
        sender.sendMessage("§7Usage: /wheel <add|list> [player]");
    }
});