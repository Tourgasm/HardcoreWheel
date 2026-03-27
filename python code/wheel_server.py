"""
Core wheel server with async WebSocket handling
"""

import asyncio
import json as json_module
import logging
import threading
import time
import uuid
from queue import Queue
from typing import Dict, Optional, Set

import requests
import socketio
from flask import Flask, request, jsonify
from flask_cors import CORS
from pytchat import create
from websockets.server import serve

from wheel_logic import spin_wheel, build_multiplier, DEFAULT_DURATIONS, ANIMATION_DELAYS, Spin, validate_donor_name, validate_amount
from wheel_config import ConfigManager, StateManager, DEFAULT_CONFIG, DEFAULT_STATE


# Setup file logging
logging.basicConfig(
    filename='wheel_server.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class WheelServer:
    """Main wheel server with threading safety"""
    
    def __init__(self, config: Optional[Dict] = None, message_queue: Optional[Queue] = None):
        """
        Initialize wheel server
        
        Args:
            config: Configuration dict (or None to load from file)
            message_queue: Queue for GUI communication (or None to create new)
        """
        # Merge config with defaults (always fill missing keys)
        base_cfg = DEFAULT_CONFIG.copy()
        loaded_cfg = ConfigManager.load() if config is None else dict(config)
        base_cfg.update(loaded_cfg)
        self.config = base_cfg
        self.message_queue = message_queue or Queue()
        
        # Load persisted state
        self.state = StateManager.load()
        
        # Create Flask app for API
        self.app = self._create_flask_app()
        
        # Threading safety
        self.state_lock = threading.Lock()
        
        # Runtime state
        self.minecraft_client = None
        self.overlay_clients: Set = set()
        self.event_loop = None
        self.is_paused = False
        self.pause_reason: Optional[str] = None
        self.last_auto_spin_time = 0
        self.last_randomizer_spin_time = 0  # For auto-spin randomizer
        self.discount_active_until = 0
        self.youtube_chat = None
        self.spin_interval = 30  # seconds between spins

    def _create_flask_app(self):
        """Create Flask API application"""
        from flask import Flask, jsonify, request
        from flask_cors import CORS
        
        app = Flask(__name__)
        try:
            CORS(app)
        except Exception:
            pass  # CORS is optional
        
        @app.get('/health')
        def health():
            return jsonify({
                'ok': True,
                'queue': len(self.state.get('spin_queue', [])),
                'paused': bool(self.is_paused),
            })
        
        @app.get('/state')
        def get_state():
            return jsonify({
                'spin_queue': self.state.get('spin_queue', [])[:100],  # Limit to prevent huge responses
                'doom_hits': self.state.get('doom_hits', 0),
                'disabled_punishments': self.state.get('disabled_punishments', []),
            })
        
        @app.post('/spin')
        def post_spin():
            """Add spin via HTTP API"""
            try:
                data = request.get_json(silent=True) or {}
                donor = validate_donor_name(data.get('donor', 'Anonymous'))
                role = str(data.get('role', 'viewer')).lower().strip()[:20]
                
                try:
                    usd_value = validate_amount(data.get('usd_value', data.get('amount', 0.0)))
                except (ValueError, TypeError):
                    return jsonify({'ok': False, 'error': 'Invalid amount'}), 400
                
                if usd_value <= 0:
                    return jsonify({'ok': False, 'error': 'Amount must be > 0'}), 400
                
                self.add_spin(donor, role, usd_value)
                return jsonify({
                    'ok': True,
                    'queued': True,
                    'queue': len(self.state.get('spin_queue', []))
                })
            except Exception as e:
                return jsonify({'ok': False, 'error': str(e)}), 500
        
        @app.post('/pause')
        def pause_spin():
            """Pause wheel"""
            self.is_paused = True
            self.pause_reason = "api"
            return jsonify({'ok': True, 'paused': True})
        
        @app.post('/resume')
        def resume_spin():
            """Resume wheel"""
            self.is_paused = False
            self.pause_reason = None
            return jsonify({'ok': True, 'paused': False})
        
        @app.get('/config')
        def get_config():
            """Get current configuration (for overlay and other clients)"""
            return jsonify({
                'ok': True,
                'PRICE_PER_SPIN': float(self.config.get('PRICE_PER_SPIN', 2.0)),
                'DISCOUNT_PRICE': float(self.config.get('DISCOUNT_PRICE', 1.0)),
                'DOOM_REQUIRED': int(self.config.get('DOOM_REQUIRED', 6)),
                'REVIVE_POINTS_COST': int(self.config.get('REVIVE_POINTS_COST', 1000)),
                'REVIVE_PRICE': float(self.config.get('REVIVE_PRICE', 5.0)),
                'SPIN_INTERVAL': int(self.config.get('SPIN_INTERVAL', 30)),
                'DISCOUNT_DURATION': int(self.config.get('DISCOUNT_DURATION', 300)),
            })
        
        return app

    def log_message(self, message: str) -> None:
        """Log to GUI and file"""
        self.message_queue.put(("log", message))
        logging.info(message)

    def get_top_killers(self, limit: int = 3) -> list:
        """Get top killers with spins and kill count"""
        killers = []
        for name, kills in self.state.get("kill_tracker", {}).items():
            killers.append({
                "name": name,
                "kills": kills,
                "spins": self.state.get("spin_tracker", {}).get(name, 0)
            })
        return sorted(killers, key=lambda x: x["kills"], reverse=True)[:limit]
    
    def add_spin(self, donor: str, role: str, usd_value: float = 0.0, use_discount: bool = False) -> None:
        """
        Add spin to queue and update trackers
        
        Args:
            donor: Donor name
            role: Donor role (viewer, member, moderator, mod+member)
            usd_value: USD amount of donation
            use_discount: Whether this spin used a discount
        """
        from dataclasses import asdict
        
        # Validate inputs
        donor = validate_donor_name(donor)
        usd_value = validate_amount(usd_value)
        
        if usd_value <= 0:
            return
        
        # Thread-safe state update
        with self.state_lock:
            spin = Spin(donor, role, usd_value)
            self.state["spin_queue"].append(asdict(spin))
            
            # Update trackers
            self.state["spin_tracker"][donor] = self.state["spin_tracker"].get(donor, 0) + 1
            self.state["donation_tracker"][donor] = self.state["donation_tracker"].get(donor, 0) + usd_value
        
        # Log and notify
        if use_discount:
            self.log_message(f"✅ Discounted spin queued: {donor} (DISCOUNT ACTIVE)")
        else:
            self.log_message(f"✅ Spin queued: {donor} ({role})")
        
        StateManager.save(self.state)
        self.message_queue.put(("queue_updated", self.state["spin_queue"]))

    def auto_process_spin(self) -> None:
        """Auto-process one spin from queue if conditions met"""
        # Defensive checks
        if not isinstance(self.state, dict):
            try:
                self.state = StateManager.load()
            except Exception:
                self.state = DEFAULT_STATE.copy()
        
        if "spin_queue" not in self.state:
            self.state["spin_queue"] = []
        
        current_time = time.time()
        
        # Rate limit to configured interval
        if current_time - self.last_auto_spin_time < self.spin_interval:
            return
        
        # Skip if paused or no queue
        if self.is_paused or not self.state["spin_queue"]:
            return
        
        # Thread-safe pop from queue
        with self.state_lock:
            if not self.state["spin_queue"]:
                return
            spin_data = self.state["spin_queue"].pop(0)
        
        self.last_auto_spin_time = current_time
        remaining = len(self.state["spin_queue"])
        
        self.log_message(f"🎡 AUTO-SPIN: {spin_data['donor']} ({remaining} remaining in queue)")
        
        try:
            wheel_result = spin_wheel()
            self.process_wheel_result(
                spin_data["donor"],
                wheel_result.__dict__,
                spin_data.get("role", "viewer")
            )
        except Exception as e:
            self.log_message(f"❌ Spin processing error: {e}")
        
        StateManager.save(self.state)
        self.message_queue.put(("queue_updated", self.state["spin_queue"]))

    def force_spin_once(self) -> None:
        """Force a single spin immediately (still respects pause state)"""
        if self.is_paused:
            self.log_message("⏸️ Wheel is paused; force spin blocked")
            return
        
        if not self.state.get("spin_queue"):
            self.log_message("ℹ️ No spins in queue to process")
            return
        
        with self.state_lock:
            if not self.state["spin_queue"]:
                return
            spin_data = self.state["spin_queue"].pop(0)
        
        remaining = len(self.state["spin_queue"])
        self.log_message(f"🎡 FORCE-SPIN: {spin_data.get('donor', 'Unknown')} ({remaining} remaining in queue)")
        
        try:
            wheel_result = spin_wheel()
            self.process_wheel_result(
                spin_data.get("donor", "Unknown"),
                wheel_result.__dict__,
                spin_data.get("role", "viewer")
            )
        except Exception as e:
            self.log_message(f"❌ Force-spin failed: {e}")
        
        try:
            StateManager.save(self.state)
            self.message_queue.put(("queue_updated", self.state["spin_queue"]))
        except Exception:
            pass

    def process_randomizer_spin(self) -> None:
        """Auto-spin randomizer without donations - triggers on interval when enabled"""
        # Check if randomizer is enabled
        if not self.config.get("RANDOMIZER_ENABLED", False):
            return
        
        # Rate limit to configured interval
        randomizer_interval = self.config.get("RANDOMIZER_INTERVAL", 30)
        current_time = time.time()
        if current_time - self.last_randomizer_spin_time < randomizer_interval:
            return
        
        # Skip if paused
        if self.is_paused:
            return
        
        self.last_randomizer_spin_time = current_time
        
        # Spin the wheel and process result
        try:
            wheel_result = spin_wheel()
            self.process_wheel_result(
                "🎲 RANDOMIZER",  # Special donor name
                wheel_result.__dict__,
                "randomizer"  # Special role
            )
            self.log_message(f"🎲 RANDOMIZER activated: {wheel_result.label}")
        except Exception as e:
            self.log_message(f"❌ Randomizer spin failed: {e}")

    def clear_bank(self) -> None:
        """Clear all spins from queue"""
        queue_size = len(self.state["spin_queue"])
        
        with self.state_lock:
            self.state["spin_queue"] = []
        
        StateManager.save(self.state)
        self.log_message(f"🗑️ Bank cleared: {queue_size} spins removed")
        self.message_queue.put(("queue_updated", self.state["spin_queue"]))

    def process_wheel_result(self, donor: str, result: Dict, role: str = "viewer") -> Dict:
        """
        Process wheel result and send to Minecraft/overlay
        
        Args:
            donor: Donor name
            result: Wheel result dict with 'action', 'label', 'meta'
            role: Donor role for multiplier
        
        Returns:
            The result dict
        """
        action = result.get("action")
        label = result.get("label", action)
        
        # Handle RANDOM_APOCALYPSE by picking a random punishment
        if action == "RANDOM_APOCALYPSE":
            import random
            disabled_list = self.state.get("disabled_punishments", [])
            available_slots = [s for s in self._get_all_slots() 
                             if s["id"] not in disabled_list and s["id"] != "RANDOM_APOCALYPSE"]
            if available_slots:
                random_slot = random.choice(available_slots)
                action = random_slot["id"]
                label = random_slot["label"]
                result["action"] = action
                result["label"] = label
                self.log_message(f"🎲 RANDOMIZER selected: {label}")
            else:
                self.log_message(f"⚠️ RANDOMIZER triggered but no available punishments!")
                return result
        
        multiplier = build_multiplier(role)
        
        self.log_message(f"🎡 Wheel result: {label} for {donor} (Role: {role}, {multiplier}x duration)")
        
        # Build overlay message with filtered slots
        disabled_list = self.state.get("disabled_punishments", [])
        filtered_slots = [s for s in self._get_all_slots() if s["id"] not in disabled_list]
        
        show_wheel_msg = {
            "type": "SHOW_WHEEL",
            "action": action,
            "donor": donor,
            "label": label,
            "multiplier": multiplier,
            "slots": filtered_slots,
            "basePrice": self.config.get("PRICE_PER_SPIN", 2.0)
        }
        self.queue_broadcast_to_overlay(show_wheel_msg)
        self.log_message(f"📺 Broadcast SHOW_WHEEL to overlay: {donor} spinning...")
        
        # Broadcast wheel result
        wheel_result_msg = {
            "type": "WHEEL_RESULT",
            "action": action,
            "label": label,
            "donor": donor,
            "multiplier": multiplier
        }
        self.queue_broadcast_to_overlay(wheel_result_msg)
        
        # Schedule punishment delivery with delay
        delay_time = ANIMATION_DELAYS["WHEEL_BASE"]
        if action == "FREE_ARMOR":
            delay_time += ANIMATION_DELAYS["ARMOR_ANIMATION"]
        
        def send_punishment_delayed():
            time.sleep(delay_time)
            
            self.queue_broadcast_to_overlay({"type": "HIDE_WHEEL"})
            self.log_message(f"📺 Broadcast HIDE_WHEEL to overlay")
            
            self.log_message(f"⏱️ Punishment delay complete, sending to Minecraft with {multiplier}x duration...")
            
            meta = self._build_punishment_meta(action)
            
            self.send_to_minecraft({
                "type": "wheel:run",
                "player": donor,
                "action": action,
                "label": label,
                "multiplier": multiplier,
                "meta": meta if meta else None
            })
        
        threading.Thread(target=send_punishment_delayed, daemon=True).start()
        self.log_message(f"⏱️ {delay_time:.1f}s punishment delay started for {donor}...")
        
        # Check for DOOM activation
        if action == "DESTROY_WORLD":
            self._handle_doom_activation(donor, multiplier)
        
        # Check for DISCOUNT activation
        elif action == "WHEEL_DISCOUNT":
            self._handle_discount_activation(donor)
        
        StateManager.save(self.state)
        return result

    def _get_all_slots(self):
        """Get all wheel slots (for filtering)"""
        return [
            {"id": "NO_ARMOR", "label": "No Armor", "color": "#e74c3c"},
            {"id": "NO_TOOLS", "label": "No Tools", "color": "#e67e22"},
            {"id": "LOSE_INVENTORY", "label": "Lose Inventory", "color": "#c0392b"},
            {"id": "WOODEN_TOOLS", "label": "Wooden Tools", "color": "#d35400"},
            {"id": "NO_EATING", "label": "No Eating", "color": "#f39c12"},
            {"id": "WHEEL_DISCOUNT", "label": "WHEEL DISCOUNT", "color": "#f1c40f"},
            {"id": "CLEANSE", "label": "Cleanse", "color": "#2ecc71"},
            {"id": "LOSE_HOTBAR", "label": "Lose Hotbar", "color": "#9b59b6"},
            {"id": "ONE_BLOCK_MODE", "label": "One Block Mode", "color": "#3498db"},
            {"id": "NO_SHELTER", "label": "No Shelter", "color": "#2980b9"},
            {"id": "SAFE", "label": "Safe", "color": "#27ae60"},
            {"id": "DESTROY_WORLD", "label": "Destroy World", "color": "#000000"},
            {"id": "NO_ATTACK", "label": "Visitor Mode", "color": "#95a5a6"},
            {"id": "MLG_CHALLENGE", "label": "MLG OR DIE", "color": "#e74c3c"},
            {"id": "CREEPER_SQUAD", "label": "CREEPER SQUAD", "color": "#2ecc71"},
            {"id": "ZOMBIE_HORDE", "label": "ZOMBIE HORDE", "color": "#16a085"},
            {"id": "COBWEB_TRAP", "label": "COBWEB TRAP", "color": "#95a5a6"},
            {"id": "PHANTOM_ATTACK", "label": "PHANTOM SQUAD", "color": "#34495e"},
            {"id": "RANDOM_STATUS", "label": "RANDOM CURSE", "color": "#9b59b6"},
            {"id": "FOOD_SCRAMBLE", "label": "FOOD ROT", "color": "#27ae60"},
            {"id": "WILD_TP", "label": "WILD TELEPORT", "color": "#8e44ad"},
            {"id": "FLOOR_IS_LAVA", "label": "FLOOR IS LAVA", "color": "#FF0000"},
            {"id": "TNT_RAIN", "label": "TNT RAIN", "color": "#FF6347"},
            {"id": "DIMENSIONAL_CHAOS", "label": "DIMENSION CHAOS", "color": "#9932cc"},
            {"id": "FREE_ARMOR", "label": "FREE ARMOR", "color": "#FFD700"},
            {"id": "JAILBREAK", "label": "JAILBREAK", "color": "#2c3e50"},
            {"id": "RANDOM_APOCALYPSE", "label": "RANDOMIZER", "color": "#663399"},
        ]

    def _build_punishment_meta(self, action: str) -> Dict:
        """Build meta data for special punishments"""
        import random
        
        meta = {}
        
        if action == "FREE_ARMOR":
            armor_tiers = ["leather", "copper", "chain", "iron", "diamond", "netherite"]
            armor_pieces = ["helmet", "chestplate", "leggings", "boots", "full_set"]
            armor_enchantments = [
                {"id": "protection", "lvl": 1},
                {"id": "protection", "lvl": 2},
                {"id": "protection", "lvl": 3},
                {"id": "protection", "lvl": 4},
                {"id": "mending", "lvl": 1},
                {"id": "unbreaking", "lvl": 1},
                {"id": "unbreaking", "lvl": 2},
                {"id": "unbreaking", "lvl": 3}
            ]
            
            meta["armorTier"] = random.choice(armor_tiers)
            meta["armorPiece"] = random.choice(armor_pieces)
            meta["enchantment"] = random.choice(armor_enchantments)
            self.log_message(f"🎁 FREE_ARMOR: {meta['armorTier'].upper()} {meta['armorPiece'].replace('_', ' ').upper()}")
        
        if action == "LOSE_HOTBAR":
            slot_options = ["ALL", 1, 2, 3, 4, 5, 6, 7, 8, 9]
            meta["slot"] = random.choice(slot_options)
            self.log_message(f"🎒 LOSE_HOTBAR: Slot {meta['slot']}")
        
        if action == "DESTROY_WORLD":
            doom_required = self.config.get("DOOM_REQUIRED", 6)
            meta["doomHits"] = self.state.get("doom_hits", 0)
            meta["doomRequired"] = doom_required
        
        return meta

    def _handle_doom_activation(self, donor: str, multiplier: float) -> None:
        """Handle DESTROY_WORLD punishment and check for DOOM activation"""
        with self.state_lock:
            self.state["doom_hits"] = self.state.get("doom_hits", 0) + 1
        
        doom_required = self.config.get("DOOM_REQUIRED", 6)
        doom_hits = self.state.get("doom_hits", 0)
        
        self.log_message(f"💀 DOOM hit #{doom_hits}/{doom_required}")
        
        if doom_hits >= doom_required:
            self.log_message("🔥🔥🔥 DOOM ACTIVATED! 🔥🔥🔥")
            
            self.queue_broadcast_to_overlay({
                "type": "doom",
                "donor": donor,
                "message": "ULTIMATE PUNISHMENT ACTIVATED"
            })
            
            def send_doom_delayed():
                time.sleep(ANIMATION_DELAYS["DOOM_DELAY"])
                self.send_to_minecraft({
                    "type": "wheel:run",
                    "player": donor,
                    "action": "DESTROY_WORLD",
                    "label": "Destroy World",
                    "multiplier": multiplier,
                    "meta": {
                        "isFinal": True,
                        "durationSeconds": 0,
                        "doomHits": doom_hits,
                        "doomRequired": doom_required
                    }
                })
            
            threading.Thread(target=send_doom_delayed, daemon=True).start()
            
            with self.state_lock:
                self.state["doom_hits"] = 0

    def _handle_discount_activation(self, donor: str) -> None:
        """Handle WHEEL_DISCOUNT result"""
        discount_duration = self.config.get("DISCOUNT_DURATION", 300)
        current_time = time.time()
        
        if hasattr(self, 'discount_active_until') and current_time < self.discount_active_until:
            self.discount_active_until += discount_duration
            self.log_message(f"🎁 DISCOUNT EXTENDED by {discount_duration}s! Total: {int(self.discount_active_until - current_time)}s")
        else:
            self.discount_active_until = current_time + discount_duration
            self.log_message(f"🎁 DISCOUNT ACTIVATED for {discount_duration}s! Everyone gets ${self.config.get('DISCOUNT_PRICE', 1.0)}/spin")
        
        remaining_time = int(self.discount_active_until - current_time)
        self.queue_broadcast_to_overlay({
            "type": "discount",
            "donor": donor,
            "duration": discount_duration,
            "remaining": remaining_time,
            "message": f"🎁 {donor.upper()} WON {discount_duration}s DISCOUNT! Total: {remaining_time}s"
        })

    def send_to_minecraft(self, data: Dict) -> None:
        """Send JSON command to Minecraft via MCWSS WebSocket"""
        if not self.minecraft_client:
            self.log_message(f"⚠️ No Minecraft connected, queuing: {data.get('type', 'unknown')}")
            return
        
        if not self.event_loop:
            self.log_message(f"⚠️ Event loop not ready, queuing: {data.get('type', 'unknown')}")
            return
        
        try:
            # Apply role multiplier to duration if applicable
            action = data.get("action")
            multiplier = data.get("multiplier", 1.0)
            
            if action and multiplier != 1.0:
                duration_map = {
                    "NO_SHELTER": int(DEFAULT_DURATIONS["noShelterSeconds"] * multiplier),
                    "NO_EATING": int(DEFAULT_DURATIONS["noEatSeconds"] * multiplier),
                    "ONE_BLOCK_MODE": int(DEFAULT_DURATIONS["oneBlockSeconds"] * multiplier),
                    "FLOOR_IS_LAVA": int(DEFAULT_DURATIONS["lavaSeconds"] * multiplier),
                }
                
                if action in duration_map:
                    if "meta" not in data:
                        data["meta"] = {}
                    data["meta"]["durationSeconds"] = duration_map[action]
                    self.log_message(f"⏱️ Applying {multiplier}x duration to {action}: {duration_map[action]}s")
            
            payload = json_module.dumps(data)
            
            command_msg = {
                "header": {
                    "version": 1,
                    "requestId": str(uuid.uuid4()),
                    "messagePurpose": "commandRequest",
                    "messageType": "commandRequest"
                },
                "body": {
                    "version": 1,
                    "commandLine": f"scriptevent wheel:run {payload}",
                    "origin": {"type": "player"}
                }
            }
            
            message = json_module.dumps(command_msg)
            
            future = asyncio.run_coroutine_threadsafe(
                self.minecraft_client.send(message),
                self.event_loop
            )
            
            self.log_message(f"📤 Sent to Minecraft via MCWSS: {data.get('type', 'unknown')}")
        except Exception as e:
            self.log_message(f"❌ Error sending to Minecraft: {str(e)}")

    def push_world_end_deaths_to_minecraft(self, threshold: int) -> None:
        """Push the Hardcore world-end deaths threshold to the Bedrock addon.

        The addon listens on scriptevent wheel:run and updates its internal threshold live.
        Range is clamped on both ends to keep behavior sane.
        """
        try:
            t = int(threshold)
        except Exception:
            t = 20
        t = max(20, min(100, t))

        # Send config update to Minecraft
        self.send_to_minecraft({
            "type": "config",
            "action": "SET_WORLD_END_DEATHS",
            "value": t
        })

        # Optional: notify overlay (if connected)
        try:
            self.queue_broadcast_to_overlay({
                "type": "world_end_deaths",
                "value": t
            })
        except Exception:
            pass

    def push_hardcore_mode_to_minecraft(self, enabled: bool) -> None:
        """Push the hardcore mode flag to the Bedrock addon.
        
        When enabled=True: Normal hardcore mode (world end + lives system active)
        When enabled=False: Regular survival mode (no world end, no lives system)
        """
        # Send config update to Minecraft
        self.send_to_minecraft({
            "type": "config",
            "action": "SET_HARDCORE_MODE",
            "value": enabled
        })
        
        # Optional: notify overlay (if connected)
        try:
            self.queue_broadcast_to_overlay({
                "type": "hardcore_mode",
                "enabled": enabled
            })
        except Exception:
            pass

    async def broadcast_to_overlay(self, data: Dict) -> None:
        """Broadcast to all connected overlay clients"""
        if self.overlay_clients:
            message = json_module.dumps(data)
            for client in self.overlay_clients:
                try:
                    await client.send(message)
                except Exception as e:
                    logging.debug(f"Overlay send error: {e}")

    def queue_broadcast_to_overlay(self, data: Dict) -> None:
        """Queue broadcast to overlay (thread-safe)"""
        if not self.overlay_clients:
            self.log_message(f"⚠️ No overlay clients connected! Cannot broadcast: {data.get('type', 'unknown')}")
            return
        
        if not self.event_loop:
            self.log_message(f"⚠️ No event loop! Cannot broadcast: {data.get('type', 'unknown')}")
            return
        
        try:
            message = json_module.dumps(data)
            message_type = data.get('type', 'unknown')
            self.log_message(f"📡 Broadcasting to {len(self.overlay_clients)} overlay client(s): {message_type}")
            
            for client in list(self.overlay_clients):
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        client.send(message),
                        self.event_loop
                    )
                except Exception as send_err:
                    self.log_message(f"⚠️ Error sending to overlay client: {str(send_err)}")
        except Exception as e:
            self.log_message(f"⚠️ Error broadcasting to overlay: {str(e)}")

    def broadcast_queue_update(self) -> None:
        """Broadcast spin queue status to overlay"""
        queue_count = len(self.state.get("spin_queue", []))
        next_up = "None"
        
        if queue_count > 0:
            next_up = self.state["spin_queue"][0].get("donor", "Unknown").upper()
        
        # Get top donors
        top_donors = []
        donor_totals = {}
        
        for spin in self.state.get("spin_queue", []):
            donor = spin.get("donor", "Unknown")
            donor_totals[donor] = donor_totals.get(donor, 0) + spin.get("usd_value", 0)
        
        sorted_donors = sorted(donor_totals.items(), key=lambda x: x[1], reverse=True)[:3]
        for donor, amount in sorted_donors:
            top_donors.append({"name": donor, "total": amount})
        
        # Get top killers
        top_killers = self.get_top_killers(3)
        
        queue_update = {
            "type": "UPDATE_QUEUE",
            "count": queue_count,
            "nextUp": next_up,
            "topDonors": top_donors,
            "topKillers": top_killers,
            "basePrice": self.config.get("PRICE_PER_SPIN", 2.0),
            "revivePrice": self.config.get("REVIVE_PRICE", 5.0),
            "revivePointsCost": int(self.config.get("REVIVE_POINTS_COST", 1000)),
            "paused": bool(self.is_paused),
            "pauseReason": self.pause_reason,
        }
        
        self.queue_broadcast_to_overlay(queue_update)

    async def start(self) -> tuple:
        """Start all servers"""
        self.event_loop = asyncio.get_event_loop()
        
        self.log_message("🚀 Starting Spartan Wheel Server...")
        
        # Start Flask API
        if self.app is not None:
            threading.Thread(
                target=lambda: self.app.run(host='0.0.0.0', port=3000, use_reloader=False, threaded=True),
                daemon=True
            ).start()
            self.log_message("🔌 Flask API running on port 3000")
        
        # Start WebSocket servers
        mc_server = await serve(self.handle_minecraft, "0.0.0.0", 3001)
        overlay_server = await serve(self.handle_overlay, "0.0.0.0", 5760)
        
        self.log_message("🔌 Minecraft WebSocket on port 3001")
        self.log_message("🔌 Overlay WebSocket on port 5760")
        
        # Start background threads
        threading.Thread(target=self.auto_spin_processor, daemon=True).start()
        
        if self.config.get("YOUTUBE_CHANNEL_ID"):
            threading.Thread(target=self.start_youtube_chat, daemon=True).start()
        
        if self.config.get("STREAMLABS_TOKEN"):
            threading.Thread(target=self.start_streamlabs, daemon=True).start()
        
        return mc_server, overlay_server

    def auto_spin_processor(self) -> None:
        """Background thread that auto-processes spins and broadcasts overlay updates"""
        last_queue_state = None
        last_broadcast = 0
        broadcast_interval = 5  # Only broadcast if 5 seconds passed OR state changed
        
        while True:
            try:
                self.auto_process_spin()
                self.process_randomizer_spin()  # Auto-spin randomizer if enabled
                
                # Only broadcast if queue state changed or broadcast interval exceeded
                current_time = time.time()
                current_queue_count = len(self.state.get("spin_queue", []))
                
                # State changed: queue size changed, or enough time passed
                state_changed = (last_queue_state != current_queue_count)
                time_exceeded = (current_time - last_broadcast >= broadcast_interval)
                
                if state_changed or time_exceeded:
                    self.broadcast_queue_update()
                    last_queue_state = current_queue_count
                    last_broadcast = current_time
                
                time.sleep(1)
            except Exception as e:
                self.log_message(f"❌ Auto-spin error: {str(e)}")
                time.sleep(2)

    async def handle_minecraft(self, websocket, path) -> None:
        """Handle Minecraft MCWSS client - receives events and sends commands"""
        from uuid import uuid4
        
        self.minecraft_client = websocket
        self.message_queue.put(("connection", ("✅ Minecraft Connected", True)))
        self.message_queue.put(("service_status", ("minecraft", "connected")))
        
        # Subscribe to PlayerMessage events
        try:
            subscribe_msg = {
                "header": {
                    "version": 1,
                    "requestId": str(uuid4()),
                    "messageType": "commandRequest",
                    "messagePurpose": "subscribe"
                },
                "body": {"eventName": "PlayerMessage"}
            }
            await websocket.send(json_module.dumps(subscribe_msg))
            self.log_message("📡 Subscribed to PlayerMessage events")
        except Exception as e:
            self.log_message(f"❌ Failed to subscribe to PlayerMessage: {e}")

        # Push current Hardcore world-end threshold to the addon on connect
        try:
            self.push_world_end_deaths_to_minecraft(int(self.config.get("WORLD_END_DEATHS", 20)))
        except Exception:
            pass
        
        # Push hardcore mode flag to the addon on connect
        try:
            self.push_hardcore_mode_to_minecraft(self.config.get("HARDCORE_MODE_ENABLED", True))
        except Exception:
            pass
        
        try:
            async for message in websocket:
                try:
                    msg = json_module.loads(message)
                    event_name = msg.get("header", {}).get("eventName", "UNKNOWN")
                    
                    if event_name == "PlayerMessage":
                        await self._handle_player_message(msg)
                    elif event_name == "ScriptEventReceived":
                        await self._handle_script_event(msg)
                except Exception as e:
                    logging.debug(f"Message processing error: {e}")
        except Exception as e:
            error_msg = str(e)
            if "no close frame received" in error_msg.lower():
                self.log_message("⏸️ Minecraft disconnected (client closed connection)")
            elif "connection closed" in error_msg.lower():
                self.log_message("⏸️ Minecraft connection closed")
            else:
                self.log_message(f"⚠️ Minecraft connection error: {error_msg[:100]}")
        finally:
            self.minecraft_client = None
            self.message_queue.put(("connection", ("❌ Minecraft Disconnected", False)))
            self.message_queue.put(("service_status", ("minecraft", "disconnected")))

    async def _handle_player_message(self, msg: Dict) -> None:
        """Handle PlayerMessage event from Minecraft"""
        player_msg = msg.get("body", {}).get("message", "")
        
        # Extract text from rawtext JSON if present
        extracted_text = player_msg
        try:
            if player_msg.startswith('{"rawtext"'):
                rawtext_obj = json_module.loads(player_msg)
                if isinstance(rawtext_obj.get("rawtext"), list) and len(rawtext_obj["rawtext"]) > 0:
                    extracted_text = rawtext_obj["rawtext"][0].get("text", player_msg)
        except Exception:
            pass
        
        # Handle death data
        if extracted_text.startswith("__DEATH_DATA__:"):
            await self._process_death_data(extracted_text)
        
        # Handle wheel pause signal
        elif extracted_text.startswith("__WHEEL_PAUSE__:"):
            await self._process_wheel_pause(extracted_text)

    async def _process_death_data(self, message_text: str) -> None:
        """Process death notification from addon"""
        try:
            from urllib.parse import unquote
            decoded_msg = unquote(message_text)
            death_json = decoded_msg.replace("__DEATH_DATA__:", "", 1)
            death_data = json_module.loads(death_json)
            donor = death_data.get("donor", "Unknown")
            kills = death_data.get("kills", 0)
            
            self.log_message(f"💀 Death recorded: {donor} has {kills} kills")
            
            with self.state_lock:
                if "kill_tracker" not in self.state:
                    self.state["kill_tracker"] = {}
                self.state["kill_tracker"][donor] = kills
            
            StateManager.save(self.state)
            self.log_message(f"✅ Saved to state file: {donor} → {kills} kills")
            
            # Update scoreboard
            await self._update_scoreboard(donor, kills)
            
            # Broadcast leaderboard
            sorted_kills = sorted(
                self.state.get("kill_tracker", {}).items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            
            leaderboard_msg = {
                "type": "UPDATE_LEADERBOARD",
                "killers": [{"name": name, "kills": count} for name, count in sorted_kills]
            }
            self.queue_broadcast_to_overlay(leaderboard_msg)
        except Exception as e:
            self.log_message(f"❌ Error parsing death data: {e}")

    async def _update_scoreboard(self, donor: str, kills: int) -> None:
        """Update Minecraft scoreboard with donor kill count"""
        try:
            escaped_donor = donor.replace('"', "'").replace('\\', '')
            scoreboard_cmd = f'scoreboard players set "{escaped_donor}" donor_kills {kills}'
            
            command_msg = {
                "header": {
                    "version": 1,
                    "requestId": str(uuid.uuid4()),
                    "messagePurpose": "commandRequest",
                    "messageType": "commandRequest"
                },
                "body": {
                    "version": 1,
                    "commandLine": scoreboard_cmd,
                    "origin": {"type": "player"}
                }
            }
            
            message = json_module.dumps(command_msg)
            future = asyncio.run_coroutine_threadsafe(
                self.minecraft_client.send(message),
                self.event_loop
            )
            self.log_message(f"📊 Updated sidebar: {donor} → {kills} kills")
        except Exception as e:
            self.log_message(f"⚠️ Error updating scoreboard: {e}")

    async def _process_wheel_pause(self, message_text: str) -> None:
        """Process wheel pause signal from Minecraft"""
        try:
            from urllib.parse import unquote
            decoded_msg = unquote(message_text)
            pause_json = decoded_msg.replace("__WHEEL_PAUSE__:", "", 1)
            pause_data = json_module.loads(pause_json)
            reason = pause_data.get("reason", "unknown")
            
            self.is_paused = True
            self.pause_reason = reason
            self.log_message(f"⏸️ Wheel auto-processing PAUSED (reason: {reason})")
            
            try:
                self.queue_broadcast_to_overlay({"type": "WHEEL_PAUSED", "reason": reason})
            except Exception:
                pass
        except Exception as e:
            self.log_message(f"⚠️ Error parsing wheel pause: {e}")

    async def _handle_script_event(self, msg: Dict) -> None:
        """Handle ScriptEventReceived from Minecraft"""
        try:
            body = msg.get("body", {}) or {}
            identifier = body.get("identifier") or body.get("eventId") or body.get("id") or body.get("name") or ""
            message_text = body.get("message") or body.get("data") or ""
            
            if identifier == "wheel:pause":
                reason = "unknown"
                try:
                    pause_data = json_module.loads(message_text) if message_text else {}
                    reason = pause_data.get("reason", reason)
                except Exception:
                    pass
                
                self.is_paused = True
                self.pause_reason = reason
                self.log_message(f"⏸️ Wheel PAUSED via ScriptEventReceived (reason: {reason})")
                
                try:
                    self.queue_broadcast_to_overlay({"type": "WHEEL_PAUSED", "reason": reason})
                except Exception:
                    pass
            
            elif identifier == "wheel:resume":
                self.is_paused = False
                self.pause_reason = None
                self.log_message("▶️ Wheel RESUMED via ScriptEventReceived")
                
                try:
                    self.queue_broadcast_to_overlay({"type": "WHEEL_RESUMED"})
                except Exception:
                    pass
        except Exception as e:
            logging.debug(f"Script event handling error: {e}")

    async def handle_overlay(self, websocket, path) -> None:
        """Handle overlay client connection"""
        self.overlay_clients.add(websocket)
        self.log_message(f"📺 Overlay connected! Total clients: {len(self.overlay_clients)}")
        self.message_queue.put(("service_status", ("overlay", "connected")))
        
        # Send current queue state
        queue_count = len(self.state.get("spin_queue", []))
        next_up = "None"
        if queue_count > 0:
            next_up = self.state["spin_queue"][0].get("donor", "Unknown").upper()
        
        queue_data = {
            "type": "UPDATE_QUEUE",
            "count": queue_count,
            "nextUp": next_up,
            "topDonors": [],
            "history": []
        }
        
        try:
            await websocket.send(json_module.dumps(queue_data))
        except Exception:
            pass
        
        try:
            async for message in websocket:
                pass
        except Exception as e:
            self.log_message(f"⚠️ Overlay error: {str(e)}")
        finally:
            self.overlay_clients.discard(websocket)
            self.log_message(f"📺 Overlay disconnected! Remaining clients: {len(self.overlay_clients)}")
            status = "connected" if len(self.overlay_clients) > 0 else "disconnected"
            self.message_queue.put(("service_status", ("overlay", status)))

    def start_youtube_chat(self, max_retries: int = 3) -> None:
        """Start YouTube chat listener with retry logic"""
        import signal
        
        # Disable signal handlers for this thread
        signal.signal = lambda *args: None
        
        for attempt in range(max_retries):
            try:
                channel_id = self.config.get("YOUTUBE_CHANNEL_ID")
                if not channel_id:
                    self.log_message("⚠️ YouTube Channel ID not configured")
                    self.message_queue.put(("service_status", ("youtube", "disabled")))
                    return
                
                video_id = self._get_live_video_id(channel_id)
                if not video_id:
                    self.log_message("⏳ YouTube Chat waiting for live stream")
                    self.message_queue.put(("service_status", ("youtube", "waiting")))
                    return
                
                self.youtube_chat = create(video_id)
                self.log_message("✅ YouTube Chat connected")
                self.message_queue.put(("service_status", ("youtube", "connected")))
                
                while True:
                    try:
                        message = self.youtube_chat.get()
                        if message:
                            self._process_youtube_chat_message(message)
                    except StopIteration:
                        break
                    except Exception as e:
                        self.log_message(f"⚠️ YouTube message error: {str(e)[:100]}")
                        time.sleep(1)
            
            except Exception as e:
                self.log_message(f"⚠️ YouTube attempt {attempt+1}/{max_retries} failed: {str(e)[:100]}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                else:
                    self.message_queue.put(("service_status", ("youtube", "failed")))

    def _get_live_video_id(self, channel_id: str) -> Optional[str]:
        """Get current live stream video ID from channel ID"""
        import re
        
        try:
            url = f"https://www.youtube.com/channel/{channel_id}/live"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', response.text)
            if match:
                video_id = match.group(1)
                self.log_message(f"🎥 Found live video ID: {video_id}")
                return video_id
            
            self.log_message("❌ No live stream found on channel")
            return None
        except Exception as e:
            self.log_message(f"❌ Error fetching live video ID: {e}")
            return None

    def _process_youtube_chat_message(self, message) -> None:
        """Process a YouTube chat message"""
        try:
            author = message.author.get("name", "Unknown") if message.author else "Unknown"
            text = message.message if hasattr(message, 'message') else str(message)
            is_mod = message.author.get("isChatModerator", False) if message.author else False
            is_member = message.author.get("isChannelMember", False) if message.author else False
            is_owner = message.author.get("isChatOwner", False) if message.author else False
            
            if is_owner:
                role = "mod+member"
            elif is_mod:
                role = "moderator"
            elif is_member:
                role = "member"
            else:
                role = "viewer"
            
            self.message_queue.put(("youtube_chat", (author, text, role)))
            self.log_message(f"💬 [{role.upper()}] {author}: {text}")

            # Handle revive commands/confirmations from chat
            try:
                self._maybe_handle_chat_revive(author, text)
            except Exception as e:
                self.log_message(f"⚠️ Revive chat parse error: {str(e)[:80]}")
        except (AttributeError, KeyError, TypeError) as e:
            logging.debug(f"YouTube message format error: {e}")

    def start_streamlabs(self) -> None:
        """Start Streamlabs donation listener"""
        try:
            sio = socketio.Client()
            
            @sio.event
            def connect():
                self.log_message("✅ Streamlabs connected")
                self.message_queue.put(("service_status", ("streamlabs", "connected")))
            
            @sio.on("event")
            def on_event(data):
                if data.get("type") in ["donation", "superchat"]:
                    self._process_streamlabs_donation(data)
            
            token = self.config.get("STREAMLABS_TOKEN")
            if not token:
                self.log_message("⚠️ Streamlabs token not configured")
                self.message_queue.put(("service_status", ("streamlabs", "disabled")))
                return
            
            sio.connect(f"https://sockets.streamlabs.com?token={token}")
            sio.wait()
        except Exception as e:
            self.log_message(f"⚠️ Streamlabs error: {str(e)[:100]}")
            self.message_queue.put(("service_status", ("streamlabs", "disconnected")))

    def _process_streamlabs_donation(self, data: Dict) -> None:
        """Process a Streamlabs donation"""
        try:
            donation = data.get("message", [{}])[0]
            donor = validate_donor_name(donation.get("name", "Anonymous"))
            
            try:
                amount = float(str(donation.get("amount", 0)).replace(",", ""))
                if amount > 100000:  # Fix for multiplier issue
                    amount = amount / 1000000
            except (ValueError, TypeError):
                amount = 0
            
            currency = donation.get("currency", "USD")
            message_text = donation.get("message", "").strip()
            usd_amount = self.convert_to_usd(amount, currency)
            usd_amount = validate_amount(usd_amount)
            
            if usd_amount <= 0:
                return
            
            # Check if this is a revival request
            player_to_revive = self.parse_revival_request(message_text)
            
            if player_to_revive:
                # REVIVAL REQUEST
                self.log_message(f"💚 REVIVAL REQUEST: {donor} reviving {player_to_revive} (${usd_amount:.2f})")
                
                # Send revival event to Minecraft
                self.send_to_minecraft({
                    "type": "revival",
                    "action": "REVIVAL",
                    "player": player_to_revive,
                    "donor": donor,
                    "amount": int(usd_amount)
                })
            else:
                # REGULAR WHEEL SPIN
                regular_price = self.config.get("PRICE_PER_SPIN", 2.0)
                discount_price = self.config.get("DISCOUNT_PRICE", 1.0)
                
                current_price = regular_price
                if hasattr(self, 'discount_active_until'):
                    remaining_discount = self.discount_active_until - time.time()
                    if remaining_discount > 0:
                        current_price = discount_price
                
                spin_count = int(usd_amount / current_price) if current_price > 0 else 0
                spin_count = min(spin_count, 50)  # Cap at 50
                
                if spin_count > 0:
                    per_spin_value = usd_amount / spin_count
                    for _ in range(spin_count):
                        self.add_spin(donor, "viewer", per_spin_value)
                    
                    self.broadcast_queue_update()
                    self.auto_process_spin()
        except Exception as e:
            self.log_message(f"❌ Streamlabs processing error: {str(e)}")

    def convert_to_usd(self, amount: float, currency: str) -> float:
        """Convert amount to USD"""
        if currency == "USD":
            return amount
        
        try:
            response = requests.get("https://open.er-api.com/v6/latest/USD", timeout=2)
            data = response.json()
            rate = data.get("rates", {}).get(currency, 1.0)
            return amount / rate if rate > 0 else amount
        except Exception:
            return amount
    
    def parse_revival_request(self, message: str) -> str:
        """Parse revival message format: 'revive PlayerName' or 'revive \"Player Name\"'
        Returns player name or None if not a revival request"""
        message_lower = message.lower().strip()
        
        if not message_lower.startswith("revive "):
            return None
        
        # Extract everything after "revive "
        player_part = message[7:].strip()
        
        # Check for quoted name (handles spaces)
        if player_part.startswith('"') and '"' in player_part[1:]:
            try:
                end_quote = player_part.index('"', 1)
                player_name = player_part[1:end_quote]
            except (ValueError, IndexError):
                return None
        else:
            # Single word player name
            player_name = player_part.split()[0] if player_part else None
        
        if player_name:
            player_name = player_name.replace('_', ' ')
            player_name = ' '.join(player_name.split())
        return player_name if player_name else None

    def _normalize_player_name(self, raw: str) -> Optional[str]:
        """Normalize a player name from chat:
        - strips quotes
        - converts underscores to spaces (alias support)
        - collapses multiple spaces
        """
        if raw is None:
            return None
        name = str(raw).strip()
        if not name:
            return None
        if (name.startswith('"') and name.endswith('"')) or (name.startswith("'") and name.endswith("'")):
            name = name[1:-1].strip()
        name = name.replace('_', ' ')
        name = ' '.join(name.split())
        return name or None

    def _parse_bang_revive(self, text: str) -> Optional[str]:
        """Parse '!revive <name>' or '!revive "name with spaces"' or '!revive name_with_spaces'."""
        if not text:
            return None
        t = text.strip()
        if not t.lower().startswith('!revive'):
            return None
        rest = t[len('!revive'):].strip()
        if not rest:
            return None
        if rest.startswith('"') and '"' in rest[1:]:
            end = rest.find('"', 1)
            return self._normalize_player_name(rest[1:end])
        if ' ' in rest:
            rest = rest.split()[0]
        return self._normalize_player_name(rest)

    def _parse_streamlabs_confirm(self, author: str, text: str) -> Optional[str]:
        """Parse Streamlabs bot confirmation like:
        '🧬 Revive queued for <target>. Hold tight, <donor>!'
        """
        if not author or not text:
            return None
        bot_name = str(self.config.get('STREAMLABS_BOT_NAME', 'streamlabs')).strip().lower()
        if str(author).strip().lower() != bot_name:
            return None

        marker = str(self.config.get('STREAMLABS_REVIVE_CONFIRM_MARKER', '🧬 Revive queued for')).strip()
        if marker not in text:
            return None

        after = text.split(marker, 1)[1].strip()
        target = after.split('.', 1)[0].strip()
        return self._normalize_player_name(target)

    def _can_accept_revival(self) -> bool:
        """Whether revival requests should be allowed right now."""
        if not self.is_paused:
            return True
        blocked = {'world_end', 'destroy_world', 'doom', 'world_destroyed'}
        reason = (self.pause_reason or '').strip().lower()
        return reason not in blocked

    def _trigger_revival(self, donor: str, player: str, source: str = 'chat', amount: Optional[float] = None, points_cost: Optional[int] = None) -> None:
        """Send revival event to Minecraft (with safety checks and consistent logging)."""
        player_name = self._normalize_player_name(player)
        if not player_name:
            return

        if not self._can_accept_revival():
            self.log_message(f"⛔ Revival blocked ({self.pause_reason}); {donor} tried to revive {player_name} via {source}")
            return

        if amount is None:
            amount = float(self.config.get('REVIVE_PRICE', 5.0))

        payload = {
            "type": "revival",
            "action": "REVIVAL",
            "player": player_name,
            "donor": donor,
            "amount": amount,
        }
        if points_cost is not None:
            payload["points"] = int(points_cost)

        self.log_message(f"✨ REVIVAL TRIGGERED ({source}): {donor} → {player_name}")
        self.send_to_minecraft(payload)

    def _maybe_handle_chat_revive(self, author: str, text: str) -> None:
        """Handle revival triggers coming from YouTube chat."""
        target = self._parse_streamlabs_confirm(author, text)
        if target:
            points_cost = int(self.config.get('REVIVE_POINTS_COST', 1000))
            self._trigger_revival(donor=str(author), player=target, source='streamlabs_confirm', points_cost=points_cost)
            return

        if not bool(self.config.get('YOUTUBE_DIRECT_REVIVE_ENABLED', False)):
            return

        target2 = self._parse_bang_revive(text)
        if target2:
            self._trigger_revival(donor=str(author), player=target2, source='direct_command')
            return

