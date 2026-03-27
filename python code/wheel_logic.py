"""
Wheel logic and game mechanics
"""

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

# All wheel enforcement durations are in SECONDS, not ticks
WHEEL_SLOTS = [
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

DEADLY_CHALLENGES = [
    "MLG_CHALLENGE", "ZOMBIE_HORDE", "CREEPER_SQUAD",
    "PHANTOM_ATTACK", "FLOOR_IS_LAVA", "TNT_RAIN", "JAILBREAK"
]

ANIMATION_DELAYS = {
    "WHEEL_BASE": 3.8,
    "ARMOR_ANIMATION": 3.0,
    "DOOM_DELAY": 3.8,
}

DEFAULT_DURATIONS = {
    "oneBlockSeconds": 60,
    "noShelterSeconds": 1200,
    "noEatSeconds": 300,
    "lavaSeconds": 30,
}


@dataclass
class Spin:
    """Represents a single spin by a donor"""
    donor: str
    role: str
    usd_value: float
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


@dataclass
class WheelResult:
    """Result from spinning the wheel"""
    action: str
    label: str = ""
    meta: Dict = field(default_factory=dict)


def spin_wheel() -> WheelResult:
    """Simulate wheel spin and return random slot"""
    slot = random.choice(WHEEL_SLOTS)
    return WheelResult(
        action=slot["id"],
        label=slot["label"],
        meta={}
    )


def build_multiplier(role: str) -> float:
    """Get duration multiplier based on donor role"""
    multipliers = {
        "viewer": 1.0,
        "member": 2.0,
        "moderator": 3.0,
        "mod+member": 4.0
    }
    return multipliers.get(role.lower(), 1.0)


def validate_donor_name(donor: str) -> str:
    """Sanitize and validate donor name"""
    if not donor:
        return "Anonymous"
    
    # Trim to 100 chars, remove dangerous characters
    name = str(donor).strip()[:100]
    
    # Replace quotes and backslashes to prevent injection
    name = name.replace('"', "'").replace('\\', '')
    
    return name if name else "Anonymous"


def validate_amount(amount: float) -> float:
    """Validate donation/spin amount"""
    try:
        val = float(amount)
        # Reasonable bounds: $0.01 to $10,000
        if 0.01 <= val <= 10000:
            return round(val, 2)
    except (ValueError, TypeError):
        pass
    
    return 0.0


def validate_spin_count(amount: float, price: float) -> int:
    """Calculate valid spin count from amount and price"""
    if price <= 0:
        return 0
    
    try:
        count = int(amount / price)
        # Cap at 50 spins per donation to prevent abuse
        return min(max(count, 0), 50)
    except (ValueError, TypeError):
        return 0
