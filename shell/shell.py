#!/usr/bin/env python3
"""
Shell - Multi-OS Unified Workspace GUI

Lightweight app drawer using tkinter. Displays all apps from all backends
in a unified grid. Sends launch requests to Router Daemon via IPC socket.

Run: python3 shell.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import socket
import os
import sys
from pathlib import Path
from PIL import Image, ImageTk
import threading
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ===== CONFIGURATION =====

SOCKET_PATH = f"/run/user/{os.getuid()}/router.sock"
REGISTRY_PATH = Path(__file__).parent.parent / "daemon" / "app_registry.json"

WINDOW_TITLE = "Multi-OS Workspace"
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
ICON_SIZE = 48
APP_GRID_COLS = 4
APP_GRID_ROWS = 3

DEBUG = False

# ===== UTILITY FUNCTIONS =====

def log_info(msg):
    logger.info(msg)

def log_error(msg):
    logger.error(msg)

def log_debug(msg):
    if DEBUG:
        logger.debug(msg)

def load_registry():
    """Load app registry from JSON file."""
    try:
        if not REGISTRY_PATH.exists():
            log_error(f"Registry not found: {REGISTRY_PATH}")
            return []
        
        with open(REGISTRY_PATH, 'r') as f:
            apps = json.load(f)
        
        log_info(f"Loaded {len(apps)} apps from registry")
        return apps
    except Exception as e:
        log_error(f"Failed to load registry: {e}")
        return []

def load_icon(icon_path, size=ICON_SIZE):
    """Load and cache an icon image."""
    try:
        if not os.path.exists(icon_path):
            # Return a placeholder if icon doesn't exist
            return None
        
        img = Image.open(icon_path)
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        log_debug(f"Failed to load icon {icon_path}: {e}")
        return None

class DaemonConnection:
    """Manages connection to Router Daemon via Unix socket."""
    
    def __init__(self):
        self.connected = False
    
    def connect(self):
        """Connect to daemon socket."""
        try:
            if not os.path.exists(SOCKET_PATH):
                log_error(f"Daemon socket not found: {SOCKET_PATH}")
                log_error("Is the Router Daemon running? Start it with: python daemon/router_daemon.py")
                return False
            
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.connect(SOCKET_PATH)
            self.connected = True
            log_info(f"Connected to daemon at {SOCKET_PATH}")
            return True
        except Exception as e:
            log_error(f"Failed to connect to daemon: {e}")
            return False
    
    def send_request(self, request_dict):
        """Send a request to daemon and get response."""
        if not self.connected:
            return None, "Not connected to daemon"
        
        try:
            request_json = json.dumps(request_dict)
            log_debug(f"Sending: {request_json}")
            
            self.socket.sendall((request_json + "\n").encode())
            
            response_data = self.socket.recv(1024).decode('utf-8').strip()
            log_debug(f"Received: {response_data}")
            
            response = json.loads(response_data)
            return response, None
        except Exception as e:
            log_error(f"Request failed: {e}")
            return None, str(e)
    
    def launch_app(self, app_id):
        """Send launch request for app."""
        request = {"action": "launch", "app_id": app_id}
        return self.send_request(request)
    
    def close(self):
        """Close connection to daemon."""
        if self.connected:
            try:
                self.socket.close()
                self.connected = False
            except:
                pass

class AppGrid:
    """Manages the app grid display."""
    
    def __init__(self, parent, apps, daemon_conn):
        self.parent = parent
        self.apps = apps
        self.daemon_conn = daemon_conn
        self.icons_cache = {}
        self.app_buttons = []
        
        # Create frame for grid
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.build_grid()
    
    def build_grid(self):
        """Build the app grid."""
        if not self.apps:
            label = ttk.Label(self.frame, text="No apps configured")
            label.pack(pady=20)
            return
        
        row = 0
        col = 0
        
        for app in self.apps:
            app_id = app.get('id')
            display_name = app.get('display_name', app_id)
            icon_path = app.get('icon_path')
            
            # Create a frame for this app
            app_frame = ttk.Frame(self.frame, relief=tk.SUNKEN, borderwidth=1)
            app_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            # Load and display icon
            icon = load_icon(icon_path, ICON_SIZE)
            if icon:
                self.icons_cache[app_id] = icon
                icon_label = tk.Label(app_frame, image=icon, bg="white")
            else:
                icon_label = tk.Label(app_frame, text="[?]", width=6, height=3, bg="white")
            
            icon_label.pack(pady=5)
            
            # Display name
            name_label = ttk.Label(app_frame, text=display_name, wraplength=60, justify=tk.CENTER)
            name_label.pack(pady=5)
            
            # Launch button
            def make_launch_handler(aid, aname):
                def handler():
                    self.launch_app(aid, aname)
                return handler
            
            launch_btn = ttk.Button(
                app_frame,
                text="Launch",
                command=make_launch_handler(app_id, display_name)
            )
            launch_btn.pack(pady=5)
            
            self.app_buttons.append((app_id, launch_btn))
            
            # Configure grid column weight
            self.frame.columnconfigure(col, weight=1)
            self.frame.rowconfigure(row, weight=1)
            
            col += 1
            if col >= APP_GRID_COLS:
                col = 0
                row += 1
    
    def launch_app(self, app_id, display_name):
        """Launch an app and show status."""
        log_info(f"Launching: {app_id}")
        
        # Show loading spinner (update button text)
        for btn_id, btn in self.app_buttons:
            if btn_id == app_id:
                btn.config(state=tk.DISABLED)
                btn.config(text="...")
                btn.update()
                break
        
        # Send request to daemon in background thread
        def launch_thread():
            response, error = self.daemon_conn.launch_app(app_id)
            
            # Re-enable button after response
            for btn_id, btn in self.app_buttons:
                if btn_id == app_id:
                    btn.config(state=tk.NORMAL)
                    btn.config(text="Launch")
                    break
            
            if error:
                messagebox.showerror("Launch Failed", f"Error: {error}")
                log_error(f"Failed to launch {app_id}: {error}")
            elif response and response.get('status') == 'ok':
                log_info(f"Successfully launched: {app_id}")
            else:
                msg = response.get('message', 'Unknown error') if response else 'No response'
                messagebox.showerror("Launch Failed", f"Daemon error: {msg}")
                log_error(f"Daemon error launching {app_id}: {msg}")
        
        thread = threading.Thread(target=launch_thread, daemon=True)
        thread.start()

class ShellWindow:
    """Main application window."""
    
    def __init__(self, root):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        
        # Connect to daemon
        self.daemon_conn = DaemonConnection()
        
        if not self.daemon_conn.connect():
            self.show_daemon_error()
            return
        
        # Load apps
        self.apps = load_registry()
        
        if not self.apps:
            self.show_no_apps_error()
            return
        
        # Build UI
        self.build_ui()
    
    def build_ui(self):
        """Build the main UI."""
        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        title_label = ttk.Label(header_frame, text=WINDOW_TITLE, font=("Arial", 16, "bold"))
        title_label.pack()
        
        subtitle_label = ttk.Label(header_frame, text="Unified Multi-OS Application Drawer")
        subtitle_label.pack()
        
        # Separator
        separator = ttk.Separator(self.root, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X)
        
        # App grid
        self.grid = AppGrid(self.root, self.apps, self.daemon_conn)
        
        # Footer
        footer_frame = ttk.Frame(self.root)
        footer_frame.pack(fill=tk.X, padx=10, pady=10)
        
        status_label = ttk.Label(footer_frame, text=f"{len(self.apps)} app(s) available")
        status_label.pack()
    
    def show_daemon_error(self):
        """Show error if daemon not running."""
        messagebox.showerror(
            "Daemon Not Running",
            "Could not connect to Router Daemon.\n\n" 
            "Please start the daemon first:\n"
            "python daemon/router_daemon.py"
        )
        self.root.quit()
    
    def show_no_apps_error(self):
        """Show error if no apps configured."""
        messagebox.showerror(
            "No Apps Configured",
            f"No apps found in registry: {REGISTRY_PATH}\n\n"
            "Copy the example: cp daemon/app_registry.json.example daemon/app_registry.json\n"
            "Edit it with your apps, then restart the shell."
        )
        self.root.quit()

def main():
    root = tk.Tk()
    app = ShellWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()
