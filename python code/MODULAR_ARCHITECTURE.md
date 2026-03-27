# Spartan Wheel Server - Modularized Architecture

## Overview

The Spartan Wheel Server has been refactored from a single 2676-line file into a clean, modular structure for better maintainability, debugging, and testing.

## Module Structure

```
python/
├── main.py                      # Entry point (~50 lines)
├── wheel_logic.py               # Game mechanics (~150 lines)
├── wheel_config.py              # Configuration & state (~150 lines)
├── wheel_server.py              # Core server (~1200 lines)
├── wheel_gui.py                 # GUI components (~250 lines) 
├── wheel_server_python.spec     # PyInstaller config (UPDATED)
└── wheel_server_python.py       # (DEPRECATED - kept for reference)
```

## Module Descriptions

### `main.py` - Entry Point
- **Purpose:** Simple entry point that ties everything together
- **Responsibilities:** 
  - Load config
  - Create server and message queue
  - Start async server in background thread
  - Launch GUI
- **Key Classes:** None (just functions)

### `wheel_logic.py` - Game Mechanics
- **Purpose:** Pure game logic with no side effects
- **Responsibilities:**
  - Wheel spin logic
  - Role multipliers
  - Input validation (donor names, amounts)
  - Duration calculations
- **Key Functions:**
  - `spin_wheel()` - Random wheel result
  - `build_multiplier(role)` - Get duration multiplier
  - `validate_donor_name()` - Sanitize donor name
  - `validate_amount()` - Validate USD amounts
  - `validate_spin_count()` - Calculate spins from amount
- **Key Classes:**
  - `Spin` - Donation spin data
  - `WheelResult` - Wheel spin result

### `wheel_config.py` - Configuration & State Management
- **Purpose:** Thread-safe config and state management
- **Responsibilities:**
  - Load/save config from `wheel_config.json`
  - Load/save state from `wheel_state.json`
  - Validate config on load (handles corrupted files)
  - Thread-safe state operations with locks
- **Key Classes:**
  - `ConfigManager` - Static methods for config management
  - `StateManager` - Thread-safe state management with locks
- **Critical Features:**
  - `StateManager._lock` - Threading lock for concurrent access
  - `StateManager.safe_get()` - Thread-safe read
  - `StateManager.safe_update()` - Thread-safe write
  - `StateManager.safe_increment()` - Thread-safe counter

### `wheel_server.py` - Core Server (~1200 lines)
- **Purpose:** Main server logic and WebSocket handlers
- **Responsibilities:**
  - Flask API endpoints
  - WebSocket handling (Minecraft, Overlay)
  - Auto-spin processing
  - Wheel result processing
  - YouTube chat integration
  - Streamlabs donation handling
  - Broadcasting to overlay
- **Key Classes:**
  - `WheelServer` - Main server class with all core logic
- **Key Methods:**
  - `add_spin()` - Queue spin
  - `process_wheel_result()` - Handle wheel outcome
  - `auto_process_spin()` - Auto-process from queue
  - `send_to_minecraft()` - Send commands via MCWSS
  - `handle_minecraft()` - WebSocket handler for Minecraft
  - `handle_overlay()` - WebSocket handler for overlay
  - `start_youtube_chat()` - YouTube chat listener
  - `start_streamlabs()` - Streamlabs donation listener
- **Critical Features:**
  - `self.state_lock` - Threading lock for state access
  - Retry logic for YouTube (3 retries)
  - Input validation on all external data
  - File logging to `wheel_server.log`

### `wheel_gui.py` - GUI Components
- **Purpose:** Tkinter GUI for server control
- **Responsibilities:**
  - Setup wizard for first-time config
  - Main control panel UI
  - Console output display
  - Service status indicators
  - Button controls (pause, resume, clear, etc.)
- **Key Classes:**
  - `SetupWizard` - First-time setup wizard
  - `WheelGUI` - Main GUI window
- **Note:** This is a minimal stub. The full GUI from the original file can be gradually refactored here.

## Critical Fixes Applied

### 1. Threading Safety ✅
- **Problem:** Multiple threads accessing `self.state` without locks → race conditions
- **Solution:** Added `StateManager._lock` and `self.state_lock` in WheelServer
- **Methods:** `safe_get()`, `safe_update()`, `safe_increment()` for atomic operations

### 2. Input Validation ✅
- **Problem:** No validation on donor names, amounts → crashes and injection attacks
- **Solution:** Added validation functions in `wheel_logic.py`
- **Functions:** `validate_donor_name()`, `validate_amount()`, `validate_spin_count()`

### 3. Config Validation ✅
- **Problem:** Corrupted JSON files crash the server silently
- **Solution:** Config validation on load with backup creation
- **File:** `wheel_config.py` - ConfigManager.load()

### 4. Error Handling ✅
- **Problem:** Flask endpoints crash on invalid input
- **Solution:** Try-catch with specific exceptions in all Flask routes
- **File:** `wheel_server.py` - `_create_flask_app()` method

### 5. Retry Logic ✅
- **Problem:** YouTube chat hangs if service is slow
- **Solution:** Max retries (3) with 5-second delays
- **File:** `wheel_server.py` - `start_youtube_chat()`

### 6. File Logging ✅
- **Problem:** All logs go to GUI only, lost if GUI crashes
- **Solution:** Added file logging to `wheel_server.log`
- **File:** `wheel_server.py` - Configured at module level

## How to Run

### Development (Direct Python)
```bash
cd python
python main.py
```

### Build Executable
```bash
cd python
python -m PyInstaller wheel_server_python.spec -y
```

The executable will be in `dist/wheel_server_python.exe`

## Migration from Old Code

The original `wheel_server_python.py` is still present but **deprecated**. To fully migrate:

1. ✅ All core functionality is in modular files
2. ✅ Critical fixes are applied
3. ⚠️ GUI needs full refactoring (currently minimal stub)
4. ⏳ Event handlers need to be split into separate module if desired

### Next Steps for Full GUI Migration
Extract the GUI code from `wheel_server_python.py` (lines 1350-2400) and refactor into `wheel_gui.py`:
- Settings tab with sliders
- Debug tab for testing
- Revival tab
- Punishment manager
- YouTube command controls

This can be done incrementally without breaking anything.

## Architecture Benefits

✅ **Easier Debugging:** Find issues in specific modules  
✅ **Better Testing:** Unit test each module independently  
✅ **Reusable Code:** Import modules in other projects  
✅ **Threading Safety:** Central state management with locks  
✅ **Maintainability:** ~300-400 lines per file vs 2676 in one  
✅ **Scalability:** Add new modules without touching existing code  

## File Sizes

| File | Lines | Purpose |
|------|-------|---------|
| main.py | ~50 | Entry point |
| wheel_logic.py | ~150 | Game mechanics |
| wheel_config.py | ~150 | Config/state |
| wheel_gui.py | ~250 | GUI (stub) |
| wheel_server.py | ~1200 | Core server |
| **Total** | **~1800** | All new modular code |

(vs 2676 lines in original monolithic file)

## Testing

To test individual modules:

```python
# Test wheel logic
from wheel_logic import spin_wheel, build_multiplier
result = spin_wheel()
print(result)  # Outputs: WheelResult with random action

# Test config
from wheel_config import ConfigManager
config = ConfigManager.load()
print(config["PRICE_PER_SPIN"])

# Test server creation
from wheel_server import WheelServer
from queue import Queue
server = WheelServer(config, Queue())
print(server.config)
```

## Known Limitations

1. **GUI is minimal stub** - Full GUI refactoring needed
2. **Handlers not yet separated** - Could split into `wheel_handlers.py` if desired
3. **Tests not included** - Add `test_wheel_*.py` files for unit tests

## Future Improvements

- [ ] Complete GUI refactoring
- [ ] Separate event handlers into `wheel_handlers.py`
- [ ] Add unit tests in `tests/` directory
- [ ] Add configuration schema validation
- [ ] Add database backend option (currently JSON files)
- [ ] Add API documentation

---

**Last Updated:** January 22, 2026  
**Status:** Modularized with critical fixes applied  
**Ready to Use:** Yes, run `python main.py`
