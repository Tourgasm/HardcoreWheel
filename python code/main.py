"""
Main entry point for Spartan Wheel Server
"""

import os

# --- Import path bootstrap (works for source + PyInstaller) ---
def _bootstrap_import_path():
    # When frozen, modules live under sys._MEIPASS; also include exe folder.
    paths = []
    try:
        if getattr(sys, 'frozen', False):
            paths.append(getattr(sys, '_MEIPASS', ''))
            paths.append(os.path.dirname(os.path.abspath(sys.argv[0])))
        else:
            paths.append(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        pass
    paths.append(os.getcwd())
    for p in paths:
        if p and p not in sys.path:
            sys.path.insert(0, p)

_bootstrap_import_path()
# ------------------------------------------------------------

import asyncio
import sys
import threading
import time
from queue import Queue

from wheel_config import ConfigManager, StateManager
from wheel_server import WheelServer


async def run_server(server: WheelServer) -> None:
    """Run server async with discount timer broadcasting"""
    await server.start()
    
    last_discount_broadcast = 0
    while True:
        await asyncio.sleep(1)
        
        # Broadcast discount timer every second if active
        current_time = time.time()
        if hasattr(server, 'discount_active_until') and current_time < server.discount_active_until:
            if current_time - last_discount_broadcast >= 1:
                remaining = int(server.discount_active_until - current_time)
                server.queue_broadcast_to_overlay({
                    "type": "discount_timer",
                    "remaining": remaining,
                    "price": server.config.get("DISCOUNT_PRICE", 1.0)
                })
                last_discount_broadcast = current_time
        elif last_discount_broadcast > 0:
            server.queue_broadcast_to_overlay({"type": "discount_ended"})
            last_discount_broadcast = 0


def main() -> None:
    """Main entry point"""
    print("=" * 70)
    print("🎡 SPARTAN WHEEL SERVER - Pure Python (Modularized)")
    print("=" * 70)
    
    # Load or create config
    config = ConfigManager.load()
    
    if not ConfigManager.is_valid(config):
        print("First-time setup required...")
        from wheel_gui import SetupWizard
        SetupWizard.run()
        config = ConfigManager.load()
    
    # Create message queue for GUI communication
    message_queue = Queue()
    
    # Create server
    server = WheelServer(config, message_queue)
    
    # Start server in background thread
    def run_async_server() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_server(server))
        finally:
            loop.close()
    
    server_thread = threading.Thread(target=run_async_server, daemon=True)
    server_thread.start()
    
    # Wait a moment then start GUI
    time.sleep(1)
    
    # Start GUI (main thread)
    try:
        from wheel_gui import WheelGUI
        gui = WheelGUI(server)
        gui.run()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        StateManager.save(server.state)
        sys.exit(0)
    except Exception as e:
        print(f"❌ GUI error: {e}")
        StateManager.save(server.state)
        sys.exit(1)


if __name__ == "__main__":
    main()