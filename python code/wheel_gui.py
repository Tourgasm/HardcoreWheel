"""
Tkinter GUI for Wheel Server with tabbed interface
Complete implementation with all 6 tabs:
- Main (console + buttons)
- Settings (sliders, pricing)
- Debug (punishment testing)
- Donation_debug (donation testing)
- Revival System (revival testing)
- YouTube Chat (chat commands)
"""

import time
import asyncio
import threading
from datetime import datetime
from tkinter import *
from tkinter import messagebox
from tkinter import scrolledtext
from tkinter import ttk
from queue import Queue

from wheel_config import ConfigManager, StateManager
from wheel_server import WheelServer


class SetupWizard:
    """First-time setup wizard"""
    
    @staticmethod
    def run():
        """Run setup wizard"""
        from wheel_config import DEFAULT_CONFIG
        
        root = Tk()
        root.title("Spartan Wheel Server - Setup")
        root.geometry("500x300")
        root.configure(bg="#121212")
        
        completed = {"status": False}
        
        Label(root, text="🎡 SPARTAN WHEEL SERVER SETUP", font=("Arial", 14, "bold"),
              fg="#4CAF50", bg="#121212").pack(pady=20)
        
        Label(root, text="Enter your configuration:", font=("Arial", 10),
              fg="#e0e0e0", bg="#121212").pack(pady=(0, 20))
        
        frame = Frame(root, bg="#121212")
        frame.pack(padx=20, pady=10)
        
        Label(frame, text="YouTube Channel ID:", fg="#e0e0e0", bg="#121212").pack(anchor="w")
        yt_entry = Entry(frame, bg="#2b2b2b", fg="#e0e0e0", width=40)
        yt_entry.pack(fill="x", pady=(0, 10))
        
        Label(frame, text="Streamlabs Token:", fg="#e0e0e0", bg="#121212").pack(anchor="w")
        sl_entry = Entry(frame, bg="#2b2b2b", fg="#e0e0e0", width=40)
        sl_entry.pack(fill="x", pady=(0, 20))
        
        def on_save():
            yt_id = yt_entry.get().strip()
            sl_token = sl_entry.get().strip()
            
            if not yt_id and not sl_token:
                messagebox.showerror("Error", "Please fill in all fields")
                return
            
            config = ConfigManager.load()
            config["YOUTUBE_CHANNEL_ID"] = yt_id
            config["STREAMLABS_TOKEN"] = sl_token
            ConfigManager.save(config)
            messagebox.showinfo("Success", "Configuration saved!")
            completed["status"] = True
            root.destroy()
        
        Button(root, text="SAVE & CONTINUE", command=on_save, bg="#4CAF50",
               fg="white", padx=20, pady=10, font=("Arial", 11, "bold")).pack(pady=20)
        
        root.mainloop()
        return completed["status"]


class WheelGUI:
    def __init__(self, server):
        self.server = server
        self.root = Tk()
        self.root.title("Spartan Wheel Server - Control Panel")
        self.root.geometry("1200x750")
        self.root.configure(bg="#121212")
        
        self.yt_cmd_enabled_var = BooleanVar(value=True)
        self.yt_cmd_prefix_var = StringVar(value="!revive")
        self.yt_cmd_cooldown_var = StringVar(value="10")
        self._yt_last_cmd_ts = {}

        self.setup_ui()
        self.update_hardcore_mode_status()
        self.process_messages()
    
    def setup_ui(self):
        """Setup full tabbed GUI interface"""
        # Title
        Label(self.root, text="🎡 SPARTAN WHEEL SERVER", font=("Arial", 16, "bold"),
              fg="#4CAF50", bg="#121212").pack(pady=10)
        
        # Status frame
        status_frame = Frame(self.root, bg="#2b2b2b", relief="ridge", bd=1)
        status_frame.pack(fill="x", padx=10, pady=5)
        
        self.status_labels = {}
        services = ["minecraft", "streamlabs", "youtube", "overlay"]
        
        for service in services:
            frame = Frame(status_frame, bg="#2b2b2b")
            frame.pack(side="left", padx=8, pady=8)
            
            label = Label(frame, text=f"⏳ {service.upper()}", font=("Arial", 9),
                         fg="#FFCC00", bg="#2b2b2b")
            label.pack()
            self.status_labels[service] = label
        
        self.service_status = {"minecraft": "waiting", "streamlabs": "waiting", "youtube": "waiting", "overlay": "waiting"}
        
        # Main frame
        main_frame = Frame(self.root, bg="#121212")
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # LEFT: Tabs
        left_frame = Frame(main_frame, bg="#121212")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill="both", expand=True, pady=(0, 10))
        
        # TAB 1: MAIN
        main_tab = Frame(self.notebook, bg="#121212")
        self.notebook.add(main_tab, text="📊 Main")
        
        main_left = Frame(main_tab, bg="#121212")
        main_left.pack(side="left", fill="both", expand=False, padx=10, pady=10)
        
        main_console_frame = Frame(main_tab, bg="#121212")
        main_console_frame.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)
        
        btn_frame = Frame(main_left, bg="#121212")
        btn_frame.pack(fill="x", pady=(0, 10))
        
        Button(btn_frame, text="🎰 FREE SPIN", command=self.on_free_spin,
               bg="#4CAF50", fg="white", padx=15, pady=10, font=("Arial", 10, "bold")).pack(pady=3)
        Button(btn_frame, text="⏸️  PAUSE", command=self.on_pause,
               bg="#FF9800", fg="white", padx=15, pady=10, font=("Arial", 10, "bold")).pack(pady=3)
        Button(btn_frame, text="▶️  RESUME", command=self.on_resume,
               bg="#2196F3", fg="white", padx=15, pady=10, font=("Arial", 10, "bold")).pack(pady=3)
        Button(btn_frame, text="🗑️  CLEAR", command=self.on_clear_bank,
               bg="#f44336", fg="white", padx=15, pady=10, font=("Arial", 10, "bold")).pack(pady=3)
        Button(btn_frame, text="🔄 RESET DOOM", command=self.on_reset_doom,
               bg="#FF5722", fg="white", padx=15, pady=10, font=("Arial", 10, "bold")).pack(pady=3)
        
        Label(main_console_frame, text="📊 CONSOLE", font=("Arial", 11, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 5))
        
        self.console = scrolledtext.ScrolledText(main_console_frame, height=20, bg="#1e1e1e",
                                                 fg="#00FF00", state="disabled", font=("Courier", 9))
        self.console.pack(fill="both", expand=True)
        
        # TAB 2: SETTINGS
        settings_tab = Frame(self.notebook, bg="#121212")
        self.notebook.add(settings_tab, text="⚙️  Settings")
        
        # Create scrollable frame for settings
        settings_canvas = Canvas(settings_tab, bg="#121212", highlightthickness=0)
        scrollbar = ttk.Scrollbar(settings_tab, orient="vertical", command=settings_canvas.yview)
        settings_inner = Frame(settings_canvas, bg="#121212")
        
        settings_inner.bind(
            "<Configure>",
            lambda e: settings_canvas.configure(scrollregion=settings_canvas.bbox("all"))
        )
        
        settings_canvas.create_window((0, 0), window=settings_inner, anchor="nw")
        settings_canvas.configure(yscrollcommand=scrollbar.set)
        
        settings_canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            settings_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        settings_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        Label(settings_inner, text="Spin Interval", font=("Arial", 10, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(10, 5))
        
        interval_frame = Frame(settings_inner, bg="#121212")
        interval_frame.pack(fill="x", pady=(0, 15))
        
        for label, seconds in [("⚡ 4s", 4), ("🔥 8s", 8), ("📺 15s", 15), ("🎬 30s", 30)]:
            def set_interval(s, srv=self.server):
                srv.spin_interval = s
                self.add_log(f"⏱️ Spin interval set to {s}s")
            Button(interval_frame, text=label, command=lambda s=seconds: set_interval(s),
                   bg="#FF9800", fg="white", padx=10, pady=6, font=("Arial", 9, "bold")).pack(side="left", padx=3)
        
        # Discount Duration buttons
        Label(settings_inner, text="Discount Duration", font=("Arial", 10, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(10, 5))
        
        discount_frame = Frame(settings_inner, bg="#121212")
        discount_frame.pack(fill="x", pady=(0, 15))
        
        discount_durations = [("⏱️ 2m (120s)", 120), ("⏱️ 5m (300s)", 300), ("⏱️ 10m (600s)", 600), ("⏱️ 15m (900s)", 900)]
        
        for label, seconds in discount_durations:
            def set_discount_duration(s, srv=self.server):
                srv.config["DISCOUNT_DURATION"] = s
                self.add_log(f"🎁 Discount duration set to {s} seconds ({s//60}m)")
            Button(discount_frame, text=label, command=lambda s=seconds: set_discount_duration(s),
                   bg="#4CAF50", fg="white", padx=10, pady=6, font=("Arial", 9, "bold")).pack(side="left", padx=3)
        
        # DOOM Threshold slider
        Label(settings_inner, text="DOOM Threshold (spins before destroy)", font=("Arial", 10, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(10, 5))
        
        doom_frame = Frame(settings_inner, bg="#121212")
        doom_frame.pack(fill="x", pady=(0, 15))
        
        self.doom_value_label = Label(doom_frame, text="6", font=("Arial", 10, "bold"),
                                       fg="#FFD700", bg="#121212", width=3)
        self.doom_value_label.pack(side="right")
        
        self.doom_slider = ttk.Scale(doom_frame, from_=1, to=20, orient="horizontal",
                                      command=lambda v: self.on_doom_threshold_change(v))
        self.doom_slider.set(self.server.config.get("DOOM_REQUIRED", 6))
        self.doom_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # World End Deaths slider (Hardcore world end threshold)
        Label(settings_inner, text="World End Deaths (total deaths before WORLD_ENDED)", font=("Arial", 10, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(10, 5))

        wed_frame = Frame(settings_inner, bg="#121212")
        wed_frame.pack(fill="x", pady=(0, 15))

        default_wed = int(self.server.config.get("WORLD_END_DEATHS", 20))
        self.world_end_deaths_value_label = Label(wed_frame, text=str(default_wed), font=("Arial", 10, "bold"),
                                                  fg="#FFD700", bg="#121212", width=4)
        self.world_end_deaths_value_label.pack(side="right")

        self.world_end_deaths_slider = ttk.Scale(
            wed_frame,
            from_=20,
            to=150,
            orient="horizontal",
            command=lambda v: self.on_world_end_deaths_change(v)
        )
        self.world_end_deaths_slider.set(default_wed)
        self.world_end_deaths_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        # Spacer for visual separation
        Label(settings_inner, text="", bg="#121212").pack(pady=5)
        
        # Spin Price slider
        Label(settings_inner, text="Price Per Spin (USD)", font=("Arial", 10, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(10, 5))
        
        spin_price_frame = Frame(settings_inner, bg="#121212")
        spin_price_frame.pack(fill="x", pady=(0, 15))
        
        self.spin_price_label = Label(spin_price_frame, text="$2.00", font=("Arial", 10, "bold"),
                                       fg="#4CAF50", bg="#121212", width=6)
        self.spin_price_label.pack(side="right")
        
        self.spin_price_slider = ttk.Scale(spin_price_frame, from_=0.5, to=10.0, orient="horizontal",
                                           command=lambda v: self.on_spin_price_change(v))
        self.spin_price_slider.set(self.server.config.get("PRICE_PER_SPIN", 2.0))
        self.spin_price_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        # Discount Price slider
        Label(settings_inner, text="Discount Price (USD)", font=("Arial", 10, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(10, 5))
        
        discount_price_frame = Frame(settings_inner, bg="#121212")
        discount_price_frame.pack(fill="x", pady=(0, 15))
        
        self.discount_price_label = Label(discount_price_frame, text="$1.00", font=("Arial", 10, "bold"),
                                          fg="#FFA500", bg="#121212", width=6)
        self.discount_price_label.pack(side="right")
        
        self.discount_price_slider = ttk.Scale(discount_price_frame, from_=0.25, to=5.0, orient="horizontal",
                                               command=lambda v: self.on_discount_price_change(v))
        self.discount_price_slider.set(self.server.config.get("DISCOUNT_PRICE", 1.0))
        self.discount_price_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        # Revive Points Cost slider
        Label(settings_inner, text="Revive Cost (Points)", font=("Arial", 10, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(10, 5))
        
        revive_points_frame = Frame(settings_inner, bg="#121212")
        revive_points_frame.pack(fill="x", pady=(0, 15))
        
        rp_min = int(self.server.config.get("REVIVE_POINTS_MIN", 500))
        rp_max = int(self.server.config.get("REVIVE_POINTS_MAX", 50000))
        rp_default = int(self.server.config.get("REVIVE_POINTS_COST", 1000))
        
        self.revive_points_label = Label(revive_points_frame, text=f"{rp_default} pts", font=("Arial", 10, "bold"),
                                         fg="#03A9F4", bg="#121212", width=10)
        self.revive_points_label.pack(side="right")
        
        self.revive_points_slider = ttk.Scale(revive_points_frame, from_=rp_min, to=rp_max, orient="horizontal",
                                              command=lambda v: self.on_revive_points_change(v))
        self.revive_points_slider.set(rp_default)
        self.revive_points_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        # Manage Punishments button
        Label(settings_inner, text="Punishment Management", font=("Arial", 10, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(15, 5))
        Button(settings_inner, text="⚙️  MANAGE PUNISHMENTS", command=self.on_manage_punishments,
               bg="#00BCD4", fg="white", padx=20, pady=8, font=("Arial", 10, "bold")).pack(fill="x", pady=(20, 0))
        
        # Randomizer (Auto-Spin) Section
        Label(settings_inner, text="🎲 Randomizer (Auto-Spin)", font=("Arial", 10, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(15, 5))
        
        randomizer_frame = Frame(settings_inner, bg="#121212")
        randomizer_frame.pack(fill="x", pady=(0, 10))
        
        self.randomizer_status = Label(randomizer_frame, text="🎲 OFF", font=("Arial", 10, "bold"),
                                       fg="#f44336", bg="#121212", width=8)
        self.randomizer_status.pack(side="right", padx=(5, 0))
        
        Button(randomizer_frame, text="🎲 TOGGLE AUTO-SPIN", command=self.on_toggle_randomizer,
               bg="#673AB7", fg="white", padx=15, pady=8, font=("Arial", 10, "bold")).pack(side="left", fill="x", expand=True)
        
        # Randomizer interval slider
        interval_frame = Frame(settings_inner, bg="#121212")
        interval_frame.pack(fill="x", pady=(5, 15))
        
        Label(interval_frame, text="Spin Interval (sec):", font=("Arial", 9),
              fg="#e0e0e0", bg="#121212").pack(side="left")
        
        self.randomizer_interval_label = Label(interval_frame, text="30", font=("Arial", 9, "bold"),
                                               fg="#FFD700", bg="#121212", width=3)
        self.randomizer_interval_label.pack(side="right")
        
        self.randomizer_interval_slider = ttk.Scale(
            interval_frame, from_=5, to=120, orient="horizontal",
            command=lambda v: self.on_randomizer_interval_change(v)
        )
        self.randomizer_interval_slider.set(self.server.config.get("RANDOMIZER_INTERVAL", 30))
        self.randomizer_interval_slider.pack(side="left", fill="x", expand=True, padx=(5, 10))
        
        # Hardcore Mode Toggle
        Label(settings_inner, text="🎮 Hardcore Mode", font=("Arial", 10, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(15, 5))
        
        hardcore_frame = Frame(settings_inner, bg="#121212")
        hardcore_frame.pack(fill="x", pady=(0, 15))
        
        self.hardcore_mode_status = Label(hardcore_frame, text="🎮 ON", font=("Arial", 10, "bold"),
                                         fg="#4CAF50", bg="#121212", width=8)
        self.hardcore_mode_status.pack(side="right", padx=(5, 0))
        
        Button(hardcore_frame, text="🎮 TOGGLE HARDCORE", command=self.on_toggle_hardcore_mode,
               bg="#FF9800", fg="white", padx=15, pady=8, font=("Arial", 10, "bold")).pack(side="left", fill="x", expand=True)
        
        # TAB 3: DEBUG
        debug_tab = Frame(self.notebook, bg="#121212")
        self.notebook.add(debug_tab, text="🐛 Debug")
        
        debug_left = Frame(debug_tab, bg="#121212")
        debug_left.pack(side="left", fill="both", expand=False, padx=10, pady=10)
        
        debug_console_frame = Frame(debug_tab, bg="#121212")
        debug_console_frame.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)
        
        Label(debug_left, text="Test Specific Punishment", font=("Arial", 10, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 5))
        
        all_punishments = [
            "NO_ARMOR", "NO_TOOLS", "LOSE_INVENTORY", "WOODEN_TOOLS", "NO_EATING",
            "WHEEL_DISCOUNT", "CLEANSE", "LOSE_HOTBAR", "ONE_BLOCK_MODE", "NO_SHELTER",
            "SAFE", "DESTROY_WORLD", "NO_ATTACK", "MLG_CHALLENGE", "CREEPER_SQUAD",
            "ZOMBIE_HORDE", "COBWEB_TRAP", "PHANTOM_ATTACK", "RANDOM_STATUS", "FOOD_SCRAMBLE",
            "WILD_TP", "FLOOR_IS_LAVA", "TNT_RAIN", "DIMENSIONAL_CHAOS", "FREE_ARMOR", "JAILBREAK"
        ]
        disabled_list = self.server.state.get("disabled_punishments", [])
        punishment_options = [p for p in all_punishments if p not in disabled_list]
        
        self.punishment_listbox = ttk.Combobox(debug_left, state="readonly", width=25)
        self.punishment_listbox["values"] = punishment_options
        self.punishment_listbox.set(punishment_options[0] if punishment_options else "")
        self.punishment_listbox.pack(fill="x", pady=(0, 10))
        
        Button(debug_left, text="🎯 TRIGGER", command=self.on_trigger_punishment,
               bg="#E91E63", fg="white", padx=15, pady=8, font=("Arial", 9, "bold")).pack(fill="x")
        
        Label(debug_console_frame, text="📊 DEBUG LOG", font=("Arial", 11, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 5))
        
        self.debug_console = scrolledtext.ScrolledText(debug_console_frame, height=20, bg="#1e1e1e",
                                                       fg="#FFD700", state="disabled", font=("Courier", 9))
        self.debug_console.pack(fill="both", expand=True)
        
        # TAB 4: DONATION DEBUG
        donation_tab = Frame(self.notebook, bg="#121212")
        self.notebook.add(donation_tab, text="💰 Donation_debug")
        
        donation_left = Frame(donation_tab, bg="#121212")
        donation_left.pack(side="left", fill="both", expand=False, padx=10, pady=10)
        
        donation_console_frame = Frame(donation_tab, bg="#121212")
        donation_console_frame.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)
        
        Label(donation_left, text="Amount (USD):", fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 3))
        self.amount_input = Entry(donation_left, bg="#2b2b2b", fg="#e0e0e0", width=15)
        self.amount_input.insert(0, "50")
        self.amount_input.pack(fill="x", pady=(0, 10))
        
        Label(donation_left, text="Donor:", fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 3))
        self.donor_input = Entry(donation_left, bg="#2b2b2b", fg="#e0e0e0", width=15)
        self.donor_input.insert(0, "TestDonor")
        self.donor_input.pack(fill="x", pady=(0, 15))
        
        # Role multiplier selection
        Label(donation_left, text="Role:", font=("Arial", 10, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 5))
        
        self.multiplier_var = "viewer"
        
        multipliers = [("👤 Viewer (1x)", "viewer"), ("👥 Member (2x)", "member"), 
                       ("🛡️ Mod (3x)", "moderator"), ("👑 Mod+Member (4x)", "mod+member")]
        
        for label, role in multipliers:
            Button(donation_left, text=label, command=lambda r=role: setattr(self, 'multiplier_var', r),
                   bg="#4CAF50", fg="white", padx=6, pady=4, font=("Arial", 8, "bold")).pack(fill="x", pady=2)
        
        Label(donation_left, text="Currencies:", font=("Arial", 10, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(15, 5))
        
        for currency in ["USD", "CAD", "EUR", "GBP", "JPY", "HKD"]:
            Button(donation_left, text=currency, command=lambda c=currency: self.test_donation(c),
                   bg="#1976D2", fg="white", padx=8, pady=4, font=("Arial", 8, "bold")).pack(fill="x", pady=2)
        
        Label(donation_console_frame, text="📊 DONATION LOG", font=("Arial", 11, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 5))
        
        self.donation_console = scrolledtext.ScrolledText(donation_console_frame, height=20, bg="#1e1e1e",
                                                          fg="#4CAF50", state="disabled", font=("Courier", 9))
        self.donation_console.pack(fill="both", expand=True)
        
        # TAB 5: REVIVAL SYSTEM
        revival_tab = Frame(self.notebook, bg="#121212")
        self.notebook.add(revival_tab, text="✨ Revival System")
        
        revival_left = Frame(revival_tab, bg="#121212")
        revival_left.pack(side="left", fill="both", expand=False, padx=10, pady=10)
        
        revival_console_frame = Frame(revival_tab, bg="#121212")
        revival_console_frame.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)
        
        # Left panel: Revival settings and testing
        Label(revival_left, text="💰 REVIVAL COST", font=("Arial", 11, "bold"),
              fg="#FFD700", bg="#121212").pack(anchor="w", pady=(0, 8))
        
        cost_frame = Frame(revival_left, bg="#121212")
        cost_frame.pack(fill="x", pady=(0, 15))
        
        self.revival_cost_label = Label(cost_frame, text="$50", font=("Arial", 10, "bold"),
                                         fg="#FFD700", bg="#121212", width=6)
        self.revival_cost_label.pack(side="right")
        
        self.revival_cost_slider = ttk.Scale(cost_frame, from_=5, to=200, orient="horizontal",
                                             command=lambda v: self.on_revival_cost_change(v))
        self.revival_cost_slider.set(self.server.config.get("REVIVAL_COST", 5))
        self.revival_cost_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        Label(revival_left, text="🎉 TEST REVIVAL", font=("Arial", 11, "bold"),
              fg="#FF6B6B", bg="#121212").pack(anchor="w", pady=(15, 8))
        
        Label(revival_left, text="Donor:", fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 3))
        self.revival_donor_input = Entry(revival_left, bg="#2b2b2b", fg="#e0e0e0", width=20)
        self.revival_donor_input.insert(0, "TestDonor")
        self.revival_donor_input.pack(fill="x", pady=(0, 8))
        
        Label(revival_left, text="Player:", fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 3))
        self.revival_player_input = Entry(revival_left, bg="#2b2b2b", fg="#e0e0e0", width=20)
        self.revival_player_input.insert(0, "PlayerName")
        self.revival_player_input.pack(fill="x", pady=(0, 8))
        
        Label(revival_left, text="Amount (USD):", fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 3))
        self.revival_amount_input = Entry(revival_left, bg="#2b2b2b", fg="#e0e0e0", width=20)
        self.revival_amount_input.insert(0, "5")
        self.revival_amount_input.pack(fill="x", pady=(0, 12))
        
        Button(revival_left, text="🎉 TEST REVIVAL", command=self.test_revival,
               bg="#FF6B6B", fg="white", padx=10, pady=8, font=("Arial", 10, "bold")).pack(fill="x", pady=(0, 20))
        
        Label(revival_left, text="📊 REVIVAL STATS", font=("Arial", 11, "bold"),
              fg="#4CAF50", bg="#121212").pack(anchor="w", pady=(0, 8))
        
        Button(revival_left, text="📈 Fetch Revival History", command=self.on_fetch_revival_stats,
               bg="#4CAF50", fg="white", padx=8, pady=6, font=("Arial", 9, "bold")).pack(fill="x")
        
        # Right panel: Revival log and history
        Label(revival_console_frame, text="📊 REVIVAL LOG", font=("Arial", 11, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 5))
        
        self.revival_console = scrolledtext.ScrolledText(revival_console_frame, height=20, bg="#1e1e1e",
                                                         fg="#00FF00", state="disabled", font=("Courier", 9))
        self.revival_console.pack(fill="both", expand=True)
        
        # TAB 6: YOUTUBE CHAT
        yt_tab = Frame(self.notebook, bg="#121212")
        self.notebook.add(yt_tab, text="💬 YouTube Chat")
        
        yt_left = Frame(yt_tab, bg="#121212")
        yt_left.pack(side="left", fill="both", expand=False, padx=10, pady=10)
        
        yt_console_frame = Frame(yt_tab, bg="#121212")
        yt_console_frame.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)
        
        Label(yt_left, text="💬 YOUTUBE CHAT", font=("Arial", 12, "bold"),
              fg="#FF0000", bg="#121212").pack(anchor="w", pady=(0, 8))
        
        Checkbutton(
            yt_left,
            text="✅ Enable !revive commands",
            variable=self.yt_cmd_enabled_var,
            fg="#e0e0e0",
            bg="#121212",
            activebackground="#121212",
            activeforeground="#e0e0e0",
            selectcolor="#121212"
        ).pack(anchor="w", pady=(0, 15))
        
        Label(yt_left, text="Command prefix:", fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 3))
        self.yt_cmd_prefix_input = Entry(yt_left, bg="#2b2b2b", fg="#e0e0e0", width=20, textvariable=self.yt_cmd_prefix_var)
        self.yt_cmd_prefix_input.pack(fill="x", pady=(0, 12))
        
        Label(yt_left, text="Cooldown (seconds):", fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 3))
        self.yt_cmd_cooldown_input = Entry(yt_left, bg="#2b2b2b", fg="#e0e0e0", width=20, textvariable=self.yt_cmd_cooldown_var)
        self.yt_cmd_cooldown_input.pack(fill="x", pady=(0, 15))
        
        Button(yt_left, text="💾 SAVE SETTINGS", command=self.on_save_yt_settings,
               bg="#4CAF50", fg="white", padx=10, pady=6, font=("Arial", 9, "bold")).pack(fill="x")
        
        Label(yt_console_frame, text="📊 CHAT LOG (Real-time)", font=("Arial", 11, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w", pady=(0, 5))
        
        self.yt_chat_console = scrolledtext.ScrolledText(yt_console_frame, height=25, bg="#0f0f0f",
                                                         fg="#00FF00", state="disabled", font=("Courier", 9))
        self.yt_chat_console.pack(fill="both", expand=True)
        self.yt_chat_console.config(state="normal")
        self.yt_chat_console.insert("end", "Waiting for YouTube chat messages...\n")
        self.yt_chat_console.config(state="disabled")
        
        # RIGHT: Wheel & Leaderboard
        right_frame = Frame(main_frame, bg="#121212")
        right_frame.pack(side="right", fill="both", expand=False)
        right_frame.config(width=350)
        
        Label(right_frame, text="🎡 Wheel", font=("Arial", 11, "bold"),
              fg="#e0e0e0", bg="#121212").pack(anchor="w")
        
        self.wheel_canvas = Canvas(right_frame, width=220, height=220, bg="#1e1e1e",
                                    highlightthickness=1, highlightbackground="#444444")
        self.wheel_canvas.pack(pady=(5, 15))
        
        self.wheel_rotation = 0
        self.draw_wheel()
        
        Label(right_frame, text="🏆 TOP KILLERS", font=("Arial", 10, "bold"),
              fg="#FFD700", bg="#121212").pack(anchor="w")
        
        self.leaderboard = scrolledtext.ScrolledText(right_frame, height=15, width=35,
                                                     bg="#1e1e1e", fg="#00FF00", state="disabled",
                                                     font=("Courier", 8))
        self.leaderboard.pack(fill="both", expand=True)
    
    def draw_wheel(self):
        """Draw spinning wheel"""
        self.wheel_canvas.delete("all")
        
        cx, cy = 110, 110
        radius = 90
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8", "#F7DC6F", "#BB8FCE"]
        
        for i, color in enumerate(colors):
            start = (360 / len(colors) * i) + self.wheel_rotation
            self.wheel_canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius,
                                        start=start, extent=360/len(colors),
                                        fill=color, outline="#333333", width=2)
        
        self.wheel_canvas.create_oval(cx-12, cy-12, cx+12, cy+12, fill="#FFD700", outline="#FFA500", width=2)
        
        self.wheel_rotation = (self.wheel_rotation + 4) % 360
        self.root.after(100, self.draw_wheel)
    
    def add_log(self, message: str):
        """Add to console"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_text = f"[{timestamp}] {message}\n"
        
        self.console.config(state="normal")
        self.console.insert("end", log_text)
        self.console.see("end")
        self.console.config(state="disabled")
    
    def update_service_status(self, service: str, status: str):
        """Update service status"""
        self.service_status[service] = status
        
        if service in self.status_labels:
            label = self.status_labels[service]
            
            if status == "connected":
                icon = "✅"
                color = "#4CAF50"
            elif status == "disconnected":
                icon = "❌"
                color = "#f44336"
            elif status == "waiting":
                icon = "⏳"
                color = "#FFCC00"
            else:
                icon = "❓"
                color = "#FF9800"
            
            label.config(text=f"{icon} {service.upper()}", fg=color)
    
    def update_status(self, status: str, color: str = "#FFCC00"):
        """Update status (legacy)"""
        pass
    
    def update_leaderboard_from_data(self, killers):
        """Update leaderboard"""
        current_data = str(killers) if killers else "empty"
        
        if not hasattr(self, '_last_leaderboard_data') or self._last_leaderboard_data != current_data:
            self._last_leaderboard_data = current_data
            
            self.leaderboard.config(state="normal")
            self.leaderboard.delete("1.0", "end")
            
            if not killers:
                self.leaderboard.insert("end", "No data yet\n")
            else:
                self.leaderboard.insert("end", "Rank  Donor       Kills  Spins\n")
                self.leaderboard.insert("end", "=" * 35 + "\n")
                
                medals = ["🥇", "🥈", "🥉"]
                for i, killer in enumerate(killers[:3]):
                    medal = medals[i] if i < len(medals) else f"{i+1}."
                    name = killer.get("name", "Unknown")[:12]
                    kills = killer.get("kills", 0)
                    spins = killer.get("spins", 0)
                    self.leaderboard.insert("end", f"{medal}  {name:<12} {kills:<6} {spins}\n")
            
            self.leaderboard.config(state="disabled")
    
    def on_free_spin(self):
        """Free spin - queues one spin at no cost"""
        # Use the configured spin price as the value (for tracking purposes)
        spin_price = self.server.config.get("PRICE_PER_SPIN", 2.0)
        self.server.add_spin("SPARTAN_BOT", "viewer", spin_price)
        self.add_log("🎰 FREE SPIN queued")
        # Kick the queue immediately
        self.server.auto_process_spin()
    
    def on_pause(self):
        """Pause"""
        self.server.is_paused = True
        self.server.pause_reason = "manual"
        try:
            self.server.queue_broadcast_to_overlay({"type": "WHEEL_PAUSED", "reason": "manual"})
        except Exception:
            pass
        self.add_log("⏸️  Wheel paused")
    
    def on_resume(self):
        """Resume"""
        self.server.is_paused = False
        self.server.pause_reason = None
        try:
            self.server.queue_broadcast_to_overlay({"type": "WHEEL_RESUMED"})
        except Exception:
            pass
        self.add_log("▶️  Wheel resumed")
    
    def on_clear_bank(self):
        """Clear the spin bank"""
        if messagebox.askyesno("Confirm", "Clear all spins from bank?"):
            self.server.clear_bank()
    
    def on_reset_doom(self):
        """Reset DOOM counter"""
        if messagebox.askyesno("Confirm DOOM Reset", "Reset DOOM counter to 0? This is permanent."):
            self.server.state["doom_hits"] = 0
            StateManager.save(self.server.state)
            self.add_log("🔄 DOOM counter reset to 0/6")
    
    def on_spin_price_change(self, value):
        """Update spin price"""
        price = round(float(value), 2)
        self.server.config["PRICE_PER_SPIN"] = price
        ConfigManager.save(self.server.config)
        self.spin_price_label.config(text=f"${price:.2f}")
        self.add_log(f"💵 Spin price changed to ${price:.2f}")
    
    def on_doom_threshold_change(self, value):
        """Update DOOM threshold"""
        threshold = int(float(value))
        self.server.config["DOOM_REQUIRED"] = threshold
        ConfigManager.save(self.server.config)
        self.doom_value_label.config(text=str(threshold))
        self.add_log(f"💀 DOOM threshold changed to {threshold} spins")

    def on_world_end_deaths_change(self, value):
        """Update Hardcore world end deaths threshold (pushed live to the addon)."""
        threshold = int(float(value))
        threshold = max(20, min(150, threshold))

        self.server.config["WORLD_END_DEATHS"] = threshold
        ConfigManager.save(self.server.config)

        # Update UI
        try:
            self.world_end_deaths_value_label.config(text=str(threshold))
        except Exception:
            pass

        # Push live to Minecraft + overlay
        try:
            self.server.push_world_end_deaths_to_minecraft(threshold)
        except Exception:
            pass

        self.add_log(f"🌍 World end threshold changed to {threshold} total deaths")
    
    def on_discount_price_change(self, value):
        """Update discount price"""
        price = round(float(value), 2)
        self.server.config["DISCOUNT_PRICE"] = price
        ConfigManager.save(self.server.config)
        self.discount_price_label.config(text=f"${price:.2f}")
        self.add_log(f"🎁 Discount price changed to ${price:.2f}")
    
    def on_revive_points_change(self, value):
        """Update revive points cost"""
        points = int(float(value))
        self.server.config["REVIVE_POINTS_COST"] = points
        ConfigManager.save(self.server.config)
        self.revive_points_label.config(text=f"{points} pts")
        self.add_log(f"✨ Revive points cost changed to {points} pts")
    
    def on_trigger_punishment(self):
        """Trigger a punishment directly for debugging"""
        punishment = self.punishment_listbox.get()
        if not punishment:
            messagebox.showerror("Error", "Please select a punishment")
            return
        
        label = punishment.replace("_", " ").title()
        player_name = self.donor_input.get() or "DebugPlayer"
        meta = {}
        
        if punishment == "DESTROY_WORLD":
            self.server.state["doom_hits"] = self.server.state.get("doom_hits", 0) + 1
            doom_required = self.server.config.get("DOOM_REQUIRED", 6)
            
            self.add_log(f"💀 DEBUG DOOM hit #{self.server.state['doom_hits']}/{doom_required}")
            
            meta["doomHits"] = self.server.state["doom_hits"]
            meta["doomRequired"] = doom_required
            
            if self.server.state["doom_hits"] >= doom_required:
                self.add_log(f"🔥🔥🔥 DOOM ACTIVATED! 🔥🔥🔥")
                meta["isFinal"] = True
                meta["durationSeconds"] = 0
                self.server.state["doom_hits"] = 0
        
        self.server.send_to_minecraft({
            "type": "wheel:run",
            "player": player_name,
            "action": punishment,
            "label": label,
            "multiplier": 1,
            "meta": meta if meta else None
        })
        
        self.add_log(f"🎯 DEBUG: Triggered {punishment} on {player_name}")
    
    def test_donation(self, currency: str):
        """Test donation using the amount field and selected currency.

        - Converts entered amount (in chosen currency) to USD using the server's conversion logic.
        - Computes spins based on current spin price (discount-aware).
        - Queues ALL spins, then kicks the auto-processor once.
        """
        try:
            raw_amount = float(self.amount_input.get() or "50")
            donor = (self.donor_input.get() or "TestDonor").strip()
            role = getattr(self, 'multiplier_var', 'viewer')

            import time as _time
            regular_price = float(self.server.config.get("PRICE_PER_SPIN", 2.0))
            discount_price = float(self.server.config.get("DISCOUNT_PRICE", 1.0))

            # Convert selected currency -> USD (so CAD 50 becomes the USD equivalent)
            usd_amount = float(self.server.convert_to_usd(raw_amount, currency))
            usd_amount = max(0.0, usd_amount)

            # Determine current spin price (discount-aware)
            current_price = regular_price
            if hasattr(self.server, 'discount_active_until') and _time.time() < self.server.discount_active_until:
                current_price = discount_price
                self.add_log(f"💰 DISCOUNT ACTIVE: using ${discount_price}/spin")

            if current_price <= 0:
                self.add_log("⚠️ Invalid spin price configuration.")
                return

            spin_count = int(usd_amount / current_price)

            self.add_log(f"💰 Test donation: {raw_amount:.2f} {currency} from {donor}")
            self.add_log(f"   → ≈ {usd_amount:.2f} USD")
            self.add_log(f"   → {spin_count} spin(s) @ ${current_price}/spin (Role: {role})")

            if spin_count < 1:
                self.add_log("⚠️ Amount too low for a spin.")
                return

            per_spin_value_usd = usd_amount / spin_count

            for _ in range(spin_count):
                self.server.add_spin(donor, role, per_spin_value_usd)

            if hasattr(self, 'donation_console'):
                self.donation_console.config(state="normal")
                self.donation_console.insert(
                    "end",
                    f"Queued {spin_count} spin(s) for {donor} ({raw_amount:.2f} {currency} ≈ {usd_amount:.2f} USD)\n"
                )
                self.donation_console.see("end")
                self.donation_console.config(state="disabled")

            # Kick the processor once (doesn't drain the whole queue)
            self.server.auto_process_spin()

        except ValueError:
            messagebox.showerror("Error", "Invalid amount")


    def test_revival(self):
        """Test a revival manually"""
        try:
            donor = self.revival_donor_input.get().strip()
            player = self.revival_player_input.get().strip()
            amount = float(self.revival_amount_input.get().strip())
            
            if not donor or not player:
                messagebox.showerror("Error", "Please enter donor and player names")
                return
            
            self.server.send_to_minecraft({
                "type": "revival",
                "action": "REVIVAL",
                "donor": donor,
                "amount": amount,
                "player": player
            })
            msg = f"✨ REVIVAL TRIGGERED: {donor} (${amount}) → {player}"
            self.add_log(msg)
            if hasattr(self, 'revival_console'):
                self.revival_console.config(state="normal")
                self.revival_console.insert("end", f"{msg}\n")
                self.revival_console.see("end")
                self.revival_console.config(state="disabled")
        
        except ValueError:
            messagebox.showerror("Error", "Amount must be a number")

    
    def on_revival_cost_change(self, value):
        """Update revival cost slider"""
        cost = round(float(value), 2)
        self.server.config["REVIVAL_COST"] = cost
        ConfigManager.save(self.server.config)
        self.revival_cost_label.config(text=f"${cost:.2f}")
        msg = f"💰 Revival cost changed to ${cost:.2f}"
        self.add_log(msg)
        if hasattr(self, 'revival_console'):
            self.revival_console.config(state="normal")
            self.revival_console.insert("end", f"{msg}\n")
            self.revival_console.see("end")
            self.revival_console.config(state="disabled")
    
    def on_fetch_revival_stats(self):
        """Fetch and display revival statistics"""
        msg = "📈 Fetching revival statistics..."
        self.add_log(msg)
        if hasattr(self, 'revival_console'):
            self.revival_console.config(state="normal")
            self.revival_console.insert("end", f"{msg}\n")
            self.revival_console.see("end")
            self.revival_console.config(state="disabled")
    
    def on_save_yt_settings(self):
        """Save YouTube settings"""
        try:
            cooldown = int(self.yt_cmd_cooldown_var.get())
            self.server.config["YT_COMMAND_COOLDOWN"] = cooldown
            self.server.config["YT_COMMAND_PREFIX"] = self.yt_cmd_prefix_var.get()
            ConfigManager.save(self.server.config)
            self.add_log(f"✅ YouTube settings saved (prefix: {self.yt_cmd_prefix_var.get()}, cooldown: {cooldown}s)")
        except ValueError:
            messagebox.showerror("Error", "Cooldown must be a number")
    
    def refresh_punishment_dropdown(self):
        """Refresh the Debug tab punishment dropdown in real-time"""
        if hasattr(self, 'punishment_listbox'):
            disabled_list = self.server.state.get("disabled_punishments", [])
            all_punishments = [
                "NO_ARMOR", "NO_TOOLS", "LOSE_INVENTORY", "WOODEN_TOOLS", "NO_EATING",
                "WHEEL_DISCOUNT", "CLEANSE", "LOSE_HOTBAR", "ONE_BLOCK_MODE", "NO_SHELTER",
                "SAFE", "DESTROY_WORLD", "NO_ATTACK", "MLG_CHALLENGE", "CREEPER_SQUAD",
                "ZOMBIE_HORDE", "COBWEB_TRAP", "PHANTOM_ATTACK", "RANDOM_STATUS", "FOOD_SCRAMBLE",
                "WILD_TP", "FLOOR_IS_LAVA", "TNT_RAIN", "DIMENSIONAL_CHAOS", "FREE_ARMOR",
                "JAILBREAK"
            ]
            punishment_options = [p for p in all_punishments if p not in disabled_list]
            self.punishment_listbox['values'] = punishment_options
            current = self.punishment_listbox.get()
            if current not in punishment_options:
                self.punishment_listbox.set(punishment_options[0] if punishment_options else "")
    
    def on_manage_punishments(self):
        """Open punishment manager popup"""
        popup = Tk()
        popup.title("Manage Punishments")
        popup.geometry("700x680")
        popup.configure(bg="#121212")
        
        Label(popup, text="⚙️ PUNISHMENT MANAGER", font=("Arial", 14, "bold"),
              fg="#00BCD4", bg="#121212").pack(pady=10)
        
        Label(popup, text="Multi-select punishments and enable/disable them",
              font=("Arial", 9), fg="#e0e0e0", bg="#121212").pack(pady=(0, 10))
        
        tree_frame = Frame(popup, bg="#121212")
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side="right", fill="y")
        
        cols = ("Punishment", "Status")
        tree = ttk.Treeview(tree_frame, columns=cols, height=25, selectmode="extended",
                            yscrollcommand=scrollbar.set)
        scrollbar.config(command=tree.yview)
        
        tree.column("#0", width=0, stretch="no")
        tree.column("Punishment", anchor="w", width=400)
        tree.column("Status", anchor="center", width=120)
        
        tree.heading("#0", text="", anchor="w")
        tree.heading("Punishment", text="Punishment", anchor="w")
        tree.heading("Status", text="Status", anchor="center")
        
        tree.tag_configure("enabled", foreground="#4CAF50")
        tree.tag_configure("disabled", foreground="#f44336")
        
        disabled_list = self.server.state.get("disabled_punishments", [])
        
        all_punishments = [
            "NO_ARMOR", "NO_TOOLS", "LOSE_INVENTORY", "WOODEN_TOOLS", "NO_EATING",
            "WHEEL_DISCOUNT", "CLEANSE", "LOSE_HOTBAR", "ONE_BLOCK_MODE", "NO_SHELTER",
            "SAFE", "DESTROY_WORLD", "NO_ATTACK", "MLG_CHALLENGE", "CREEPER_SQUAD",
            "ZOMBIE_HORDE", "COBWEB_TRAP", "PHANTOM_ATTACK", "RANDOM_STATUS", "FOOD_SCRAMBLE",
            "WILD_TP", "FLOOR_IS_LAVA", "TNT_RAIN", "DIMENSIONAL_CHAOS", "FREE_ARMOR",
            "JAILBREAK"
        ]
        
        for punishment in all_punishments:
            if punishment in disabled_list:
                status = "● DISABLED"
                tag = "disabled"
            else:
                status = "● ENABLED"
                tag = "enabled"
            tree.insert("", "end", text=punishment, values=(punishment, status), tags=(tag,))
        
        tree.pack(fill="both", expand=True)
        
        btn_frame = Frame(popup, bg="#121212")
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        def on_enable():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("Info", "Select punishments to enable")
                return
            disabled_list = self.server.state.get("disabled_punishments", [])
            for item in selected:
                punishment = tree.item(item)["values"][0]
                if punishment in disabled_list:
                    disabled_list.remove(punishment)
                tree.item(item, values=(punishment, "● ENABLED"), tags=("enabled",))
            self.server.state["disabled_punishments"] = disabled_list
            StateManager.save(self.server.state)
            self.add_log(f"✅ Enabled {len(selected)} punishment(s)")
            self.refresh_punishment_dropdown()
            try:
                self.server.queue_broadcast_to_overlay({
                    "type": "disabled_punishments_update",
                    "disabled_punishments": disabled_list
                })
            except:
                pass
        
        def on_disable():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("Info", "Select punishments to disable")
                return
            disabled_list = self.server.state.get("disabled_punishments", [])
            for item in selected:
                punishment = tree.item(item)["values"][0]
                if punishment not in disabled_list:
                    disabled_list.append(punishment)
                tree.item(item, values=(punishment, "● DISABLED"), tags=("disabled",))
            self.server.state["disabled_punishments"] = disabled_list
            StateManager.save(self.server.state)
            self.add_log(f"❌ Disabled {len(selected)} punishment(s)")
            self.refresh_punishment_dropdown()
            try:
                self.server.queue_broadcast_to_overlay({
                    "type": "disabled_punishments_update",
                    "disabled_punishments": disabled_list
                })
            except:
                pass
        
        def on_enable_all():
            self.server.state["disabled_punishments"] = []
            StateManager.save(self.server.state)
            for item in tree.get_children():
                punishment = tree.item(item)["values"][0]
                tree.item(item, values=(punishment, "● ENABLED"), tags=("enabled",))
            self.add_log("✅ Enabled ALL punishments")
            self.refresh_punishment_dropdown()
            try:
                self.server.queue_broadcast_to_overlay({
                    "type": "disabled_punishments_update",
                    "disabled_punishments": []
                })
            except:
                pass
        
        def on_disable_all():
            disabled_list = [tree.item(item)["values"][0] for item in tree.get_children()]
            self.server.state["disabled_punishments"] = disabled_list
            StateManager.save(self.server.state)
            for item in tree.get_children():
                punishment = tree.item(item)["values"][0]
                tree.item(item, values=(punishment, "● DISABLED"), tags=("disabled",))
            self.add_log("❌ Disabled ALL punishments")
            self.refresh_punishment_dropdown()
            try:
                self.server.queue_broadcast_to_overlay({
                    "type": "disabled_punishments_update",
                    "disabled_punishments": disabled_list
                })
            except:
                pass
        
        Button(btn_frame, text="✅ ENABLE", command=on_enable,
               bg="#4CAF50", fg="white", padx=12, pady=6, font=("Arial", 9, "bold")).pack(side="left", padx=3)
        Button(btn_frame, text="❌ DISABLE", command=on_disable,
               bg="#f44336", fg="white", padx=12, pady=6, font=("Arial", 9, "bold")).pack(side="left", padx=3)
        Button(btn_frame, text="✅ ENABLE ALL", command=on_enable_all,
               bg="#66BB6A", fg="white", padx=12, pady=6, font=("Arial", 9, "bold")).pack(side="left", padx=3)
        Button(btn_frame, text="❌ DISABLE ALL", command=on_disable_all,
               bg="#EF5350", fg="white", padx=12, pady=6, font=("Arial", 9, "bold")).pack(side="left", padx=3)

    def on_toggle_randomizer(self):
        """Toggle randomizer (auto-spin) mode"""
        randomizer_enabled = self.server.config.get("RANDOMIZER_ENABLED", False)
        randomizer_enabled = not randomizer_enabled
        
        self.server.config["RANDOMIZER_ENABLED"] = randomizer_enabled
        ConfigManager.save(self.server.config)
        
        if randomizer_enabled:
            self.randomizer_status.config(text="🎲 ON", fg="#4CAF50")
            interval = self.server.config.get("RANDOMIZER_INTERVAL", 30)
            self.add_log(f"🎲 Randomizer ENABLED - Spins every {interval}s (no donations needed)")
        else:
            self.randomizer_status.config(text="🎲 OFF", fg="#f44336")
            self.add_log("🎲 Randomizer DISABLED")

    def on_randomizer_interval_change(self, value):
        """Update randomizer spin interval"""
        interval = int(float(value))
        interval = max(5, min(120, interval))  # Clamp to 5-120 seconds
        
        self.server.config["RANDOMIZER_INTERVAL"] = interval
        ConfigManager.save(self.server.config)
        self.randomizer_interval_label.config(text=str(interval))
        self.add_log(f"🎲 Randomizer interval set to {interval}s")

    def on_toggle_hardcore_mode(self):
        """Toggle hardcore mode (world end + lives system)"""
        hardcore_enabled = self.server.config.get("HARDCORE_MODE_ENABLED", True)
        hardcore_enabled = not hardcore_enabled
        
        self.server.config["HARDCORE_MODE_ENABLED"] = hardcore_enabled
        ConfigManager.save(self.server.config)
        
        # Push to Minecraft immediately
        try:
            self.server.push_hardcore_mode_to_minecraft(hardcore_enabled)
        except Exception as e:
            self.add_log(f"⚠️ Could not push to Minecraft: {e}")
        
        if hardcore_enabled:
            self.hardcore_mode_status.config(text="🎮 ON", fg="#4CAF50")
            self.add_log("🎮 Hardcore mode ENABLED - World end and lives system active")
        else:
            self.hardcore_mode_status.config(text="🎮 OFF", fg="#f44336")
            self.add_log("🎮 Hardcore mode DISABLED - Regular survival mode (no world end, no lives)")
    
    def update_hardcore_mode_status(self):
        """Update the hardcore mode status label based on current config"""
        hardcore_enabled = self.server.config.get("HARDCORE_MODE_ENABLED", True)
        randomizer_enabled = self.server.config.get("RANDOMIZER_ENABLED", False)
        
        if hardcore_enabled:
            self.hardcore_mode_status.config(text="🎮 ON", fg="#4CAF50")
        else:
            self.hardcore_mode_status.config(text="🎮 OFF", fg="#f44336")
        
        if randomizer_enabled:
            self.randomizer_status.config(text="🎲 ON", fg="#4CAF50")
        else:
            self.randomizer_status.config(text="🎲 OFF", fg="#f44336")
    
    def process_messages(self):
        """Process messages from server"""
        try:
            for _ in range(50):
                msg_type, data = self.server.message_queue.get_nowait()
                
                if msg_type == "log":
                    self.add_log(data)
                elif msg_type == "connection":
                    status, connected = data
                    color = "#4CAF50" if connected else "#f44336"
                    self.update_status(status, color)
                elif msg_type == "service_status":
                    service, status = data
                    self.update_service_status(service, status)
                elif msg_type == "update_leaderboard":
                    if "killers" in data:
                        self.update_leaderboard_from_data(data["killers"])
                    self.server.queue_broadcast_to_overlay(data)
        except:
            pass
        
        # Schedule next check
        self.root.after(1000, self.process_messages)
    
    def run(self):
        """Run GUI"""
        self.root.mainloop()
