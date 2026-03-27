// entry.js - single script entry point required by Bedrock (only one script module allowed)
// We import the independent systems so their subscriptions/initializers register.

import "./bridge.js";   // Spartan Wheel system
import "./main.js";     // Hardcore lives/death system
// NOTE: wheelCommands.js is intentionally NOT imported.
// It used an event API that isn't present in some 1.21 builds, which can crash the pack at load.
// If you want chat/command helpers later, we'll re-add it with a compatible API.
// revival.js is imported by main.js
