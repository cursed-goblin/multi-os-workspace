#!/usr/bin/env python3
"""
Router Daemon - Multi-OS Unified Workspace

The central brain of the system. Manages:
- Windows VM lifecycle (overlay creation, boot, shutdown)
- Waydroid container lifecycle and data reset
- App launching across all three backends (Linux, Windows, Android)
- Network access control (firewall rules per backend)
- IPC communication with Shell GUI via Unix domain socket

Run: python3 router_daemon.py
"""

import json
import socket
import os
import sys
import subprocess
import signal
import time
import logging
from pathlib import Path
from datetime import datetime
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ===== CONFIGURATION =====

VM_NAME = "winvm"
VM_BASE_IMAGE = "/var/lib/libvirt/images/winvm-base.qcow2"
VM_OVERLAY_DIR = "/tmp"

WAYDROID_DATA_DIR = "/var/lib/waydroid"
WAYDROID_BACKUP_DIR = "/var/lib/waydroid-clean-backup"

SOCKET_PATH = f"/run/user/{os.getuid()}/router.sock"

# Network isolation: subnets for each backend
VM_SUBNET = "192.168.100.0/24"
VM_INTERFACE = "virbr-isolated"
WAYDROID_SUBNET = "192.168.240.0/24"
WAYDROID_INTERFACE = "waydroid0"

# Registry file
REGISTRY_PATH = Path(__file__).parent / "app_registry.json"

DEBUG = False

# ===== STATE =====

app_registry = []
session_id = str(uuid.uuid4())[:8]
vm_overlay_path = None
vm_running = False
waydroid_running = False
network_rules_added = {"vm": False, "waydroid": False}

# ===== UTILITY FUNCTIONS =====

def log_info(msg):
    logger.info(msg)

def log_error(msg):
    logger.error(msg)

def log_debug(msg):
    if DEBUG:
        logger.debug(msg)

def run_command(cmd, check=True, capture=False):
    """Run shell command, optionally capturing output."""
    try:
        if isinstance(cmd, str):
            cmd = cmd.split()
        
        log_debug(f"Running: {' '.join(cmd)}")
        
        if capture:
            result = subprocess.run(cmd, check=check, capture_output=True, text=True, timeout=10)
            return result.stdout.strip(), result.returncode
        else:
            result = subprocess.run(cmd, check=check, timeout=10)
            return None, result.returncode
    except subprocess.TimeoutExpired:
        log_error(f"Command timed out: {' '.join(cmd)}")
        return None, -1
    except Exception as e:
        log_error(f"Command failed: {e}")
        return None, -1

def load_registry():
    """Load app registry from JSON file."""
    global app_registry
    try:
        if not REGISTRY_PATH.exists():
            log_error(f"Registry file not found: {REGISTRY_PATH}")
            return False
        
        with open(REGISTRY_PATH, 'r') as f:
            app_registry = json.load(f)
        
        log_info(f"Loaded {len(app_registry)} apps from registry")
        return True
    except Exception as e:
        log_error(f"Failed to load registry: {e}")
        return False

def find_app(app_id):
    """Find app in registry by ID."""
    for app in app_registry:
        if app.get('id') == app_id:
            return app
    return None

# ===== VM MANAGEMENT =====

def create_vm_overlay():
    """Create a fresh overlay disk from base image."""
    global vm_overlay_path
    
    log_info("Creating Windows VM overlay disk...")
    
    if not os.path.exists(VM_BASE_IMAGE):
        log_error(f"Base image not found: {VM_BASE_IMAGE}")
        return False
    
    vm_overlay_path = os.path.join(VM_OVERLAY_DIR, f"winvm-overlay-{session_id}.qcow2")
    
    try:
        cmd = [
            "qemu-img", "create",
            "-f", "qcow2",
            "-b", VM_BASE_IMAGE,
            "-F", "qcow2",
            vm_overlay_path
        ]
        _, rc = run_command(cmd, capture=True)
        
        if rc == 0:
            log_info(f"Overlay created: {vm_overlay_path}")
            return True
        else:
            log_error(f"Failed to create overlay")
            return False
    except Exception as e:
        log_error(f"Error creating overlay: {e}")
        return False

def update_vm_config():
    """Update VM configuration to use the overlay disk."""
    log_info("Updating VM configuration...")
    
    try:
        # Dump current VM XML
        xml_dump, rc = run_command(f"virsh dumpxml {VM_NAME}", capture=True)
        if rc != 0:
            log_error("Failed to dump VM XML")
            return False
        
        # Replace disk path (simple text replacement)
        new_xml = xml_dump.replace(
            "<source file='/tmp/winvm-overlay",
            f"<source file='{vm_overlay_path}"
        )
        
        # Write to temp file and redefine VM
        temp_xml = f"/tmp/winvm-config-{session_id}.xml"
        with open(temp_xml, 'w') as f:
            f.write(new_xml)
        
        _, rc = run_command(f"virsh define {temp_xml}")
        os.remove(temp_xml)
        
        if rc == 0:
            log_info("VM configuration updated")
            return True
        else:
            log_error("Failed to update VM configuration")
            return False
    except Exception as e:
        log_error(f"Error updating VM config: {e}")
        return False

def start_vm():
    """Start the Windows VM."""
    global vm_running
    
    log_info(f"Starting Windows VM '{VM_NAME}'...")
    
    # Check if already running
    output, rc = run_command(f"virsh list", capture=True)
    if VM_NAME in output and "running" in output:
        log_info("VM is already running")
        vm_running = True
        return True
    
    _, rc = run_command(f"virsh start {VM_NAME}")
    
    if rc == 0:
        time.sleep(2)  # Wait for VM to fully boot
        log_info("VM started successfully")
        vm_running = True
        return True
    else:
        log_error("Failed to start VM")
        return False

def stop_vm():
    """Stop the Windows VM."""
    global vm_running
    
    log_info(f"Stopping Windows VM '{VM_NAME}'...")
    
    _, rc = run_command(f"virsh destroy {VM_NAME}", check=False)
    
    if rc == 0:
        vm_running = False
        log_info("VM stopped")
        return True
    else:
        # VM might already be stopped
        vm_running = False
        return True

def cleanup_vm_overlay():
    """Delete the overlay disk file."""
    global vm_overlay_path
    
    if vm_overlay_path and os.path.exists(vm_overlay_path):
        log_info(f"Deleting overlay: {vm_overlay_path}")
        try:
            os.remove(vm_overlay_path)
            vm_overlay_path = None
            return True
        except Exception as e:
            log_error(f"Failed to delete overlay: {e}")
            return False
    return True

# ===== WAYDROID MANAGEMENT =====

def reset_waydroid_data():
    """Reset Waydroid data directory from backup."""
    log_info("Resetting Waydroid data...")
    
    if not os.path.exists(WAYDROID_BACKUP_DIR):
        log_error(f"Waydroid backup not found: {WAYDROID_BACKUP_DIR}")
        log_error("Run: bash setup/prepare-waydroid.sh")
        return False
    
    # Stop any running session
    run_command("waydroid session stop", check=False)
    time.sleep(1)
    
    # Remove current data
    if os.path.exists(WAYDROID_DATA_DIR):
        try:
            import shutil
            shutil.rmtree(WAYDROID_DATA_DIR)
            log_debug("Deleted current Waydroid data")
        except Exception as e:
            log_error(f"Failed to delete Waydroid data: {e}")
            return False
    
    # Restore from backup (requires sudo)
    try:
        cmd = f"sudo cp -r {WAYDROID_BACKUP_DIR} {WAYDROID_DATA_DIR}"
        subprocess.run(cmd, shell=True, check=True, timeout=30)
        log_info("Waydroid data restored from backup")
        return True
    except Exception as e:
        log_error(f"Failed to restore Waydroid: {e}")
        return False

def start_waydroid():
    """Start Waydroid session."""
    global waydroid_running
    
    log_info("Starting Waydroid session...")
    
    _, rc = run_command("waydroid session start", check=False)
    
    if rc == 0:
        time.sleep(3)  # Wait for session to fully start
        log_info("Waydroid session started")
        waydroid_running = True
        return True
    else:
        log_error("Failed to start Waydroid session")
        return False

def stop_waydroid():
    """Stop Waydroid session."""
    global waydroid_running
    
    log_info("Stopping Waydroid session...")
    
    _, rc = run_command("waydroid session stop", check=False)
    
    waydroid_running = False
    log_info("Waydroid stopped")
    return True

# ===== NETWORK MANAGEMENT =====

def enable_network(backend):
    """Enable network access for a backend (VM or Waydroid)."""
    global network_rules_added
    
    if network_rules_added.get(backend):
        log_debug(f"{backend} network already enabled")
        return True
    
    log_info(f"Enabling network access for {backend}...")
    
    try:
        if backend == "vm":
            subnet = VM_SUBNET
            interface = VM_INTERFACE
        elif backend == "waydroid":
            subnet = WAYDROID_SUBNET
            interface = WAYDROID_INTERFACE
        else:
            return False
        
        # Try nftables first, fall back to iptables
        # This adds a rule allowing traffic from the subnet to the internet
        cmd = f"sudo iptables -I FORWARD -i {interface} -j ACCEPT"
        _, rc = run_command(cmd, check=False)
        
        if rc == 0:
            network_rules_added[backend] = True
            log_info(f"Network enabled for {backend}")
            return True
        else:
            log_error(f"Failed to enable network for {backend}")
            return False
    except Exception as e:
        log_error(f"Error enabling network: {e}")
        return False

def disable_network(backend):
    """Disable network access for a backend."""
    global network_rules_added
    
    if not network_rules_added.get(backend):
        return True
    
    log_info(f"Disabling network access for {backend}...")
    
    try:
        if backend == "vm":
            interface = VM_INTERFACE
        elif backend == "waydroid":
            interface = WAYDROID_INTERFACE
        else:
            return False
        
        cmd = f"sudo iptables -D FORWARD -i {interface} -j ACCEPT"
        _, rc = run_command(cmd, check=False)
        
        network_rules_added[backend] = False
        log_info(f"Network disabled for {backend}")
        return True
    except Exception as e:
        log_error(f"Error disabling network: {e}")
        return False

# ===== APP LAUNCHING =====

def launch_linux_app(app):
    """Launch a Linux native application.
    
    FIX #1: Use shell=True with a string, not a list.
    Linux apps run directly on the host with no backend-specific network handling.
    """
    app_id = app.get('id')
    launch_target = app.get('launch_target')
    
    log_info(f"Launching Linux app: {app_id} -> {launch_target}")
    
    try:
        # Use shell=True with a STRING (not a list)
        # This properly passes the command to /bin/sh -c
        subprocess.Popen(launch_target, shell=True, 
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        log_error(f"Failed to launch Linux app: {e}")
        return False

def launch_android_app(app):
    """Launch an Android app via Waydroid.
    
    Only enable network for the Android backend if needed.
    Do NOT call enable_network for other backends.
    """
    app_id = app.get('id')
    package_name = app.get('launch_target')
    needs_network = app.get('needs_network', False)
    
    log_info(f"Launching Android app: {app_id} ({package_name})")
    
    # Enable network ONLY for this backend if needed
    if needs_network:
        if not enable_network("waydroid"):
            log_error("Failed to enable network for Waydroid")
            return False
    
    try:
        cmd = f"waydroid app launch {package_name}"
        _, rc = run_command(cmd, check=False)
        
        if rc == 0:
            log_info(f"Android app launched: {app_id}")
            return True
        else:
            log_error(f"Failed to launch Android app: {app_id}")
            return False
    except Exception as e:
        log_error(f"Error launching Android app: {e}")
        return False

def launch_windows_app(app):
    """Launch a Windows app via QEMU Guest Agent and SPICE.
    
    FIX #2: Launch app once (Step 1), then call helper to maximize existing window.
    Previously was launching twice: once in guest-exec, once in the helper script.
    
    FIX #3: Only enable network for the VM backend if needed.
    """
    app_id = app.get('id')
    exe_path = app.get('launch_target')
    needs_network = app.get('needs_network', False)
    display_name = app.get('display_name', app_id)
    
    log_info(f"Launching Windows app: {app_id} -> {exe_path}")
    
    # Enable network ONLY for this backend if needed
    if needs_network:
        if not enable_network("vm"):
            log_error("Failed to enable network for VM")
            return False
    
    try:
        # Step 1: Send guest-exec command to launch the app (ONLY ONCE)
        log_debug(f"Sending guest-exec to VM for: {exe_path}")
        
        # Escape backslashes for JSON
        escaped_path = exe_path.replace("\\", "\\\\")
        
        json_cmd = json.dumps({
            "execute": "guest-exec",
            "arguments": {
                "path": escaped_path
            }
        })
        
        cmd = f'virsh qemu-agent-command {VM_NAME} \'{json_cmd}\''
        output, rc = run_command(cmd, check=False, capture=True)
        
        if rc != 0:
            log_error(f"Guest-exec failed: {output}")
            return False
        
        log_debug("App launched, waiting for window to appear...")
        time.sleep(2)
        
        # Step 2: Call helper script to maximize the ALREADY-RUNNING app window
        # (NOT re-launching the app)
        log_debug("Calling window helper script to maximize window...")
        
        # The helper script takes the app path as parameter
        # It finds the window and maximizes it (doesn't re-launch)
        helper_json = json.dumps({
            "execute": "guest-exec",
            "arguments": {
                "path": "powershell.exe",
                "arg": ["powershell.exe", "C:\\runner.ps1", escaped_path]
            }
        })
        
        cmd = f'virsh qemu-agent-command {VM_NAME} \'{helper_json}\''
        _, rc = run_command(cmd, check=False, capture=True)
        
        # Helper failure is non-critical
        time.sleep(1)
        
        # Step 3: Open SPICE client window
        log_info("Opening SPICE display...")
        
        # Use virt-viewer to display the VM (list mode = no window chrome)
        # Run in background
        subprocess.Popen(
            ["virt-viewer", "--kiosk", "--fullscreen", VM_NAME],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        time.sleep(1)
        
        # Step 4: Rename window to match app name (best effort with wmctrl)
        try:
            # Find and rename the virt-viewer window
            cmd = f"wmctrl -l | grep virt-viewer | awk '{{print $1}}'"
            window_id, _ = run_command(cmd, check=False, capture=True)
            if window_id:
                rename_cmd = f"wmctrl -i -r {window_id} -b add,maximized_vert,maximized_horz -N {display_name}"
                run_command(rename_cmd, check=False)
        except:
            pass  # Window renaming is non-critical
        
        log_info(f"Windows app launched: {app_id}")
        return True
        
    except Exception as e:
        log_error(f"Error launching Windows app: {e}")
        return False

def launch_app(app_id):
    """Main app launcher dispatcher."""
    app = find_app(app_id)
    
    if not app:
        log_error(f"App not found: {app_id}")
        return False
    
    backend = app.get('backend')
    
    if backend == 'linux':
        return launch_linux_app(app)
    elif backend == 'android':
        return launch_android_app(app)
    elif backend == 'windows':
        return launch_windows_app(app)
    else:
        log_error(f"Unknown backend: {backend}")
        return False

# ===== IPC SERVER =====

def handle_client(client_socket, addr):
    """Handle a single client connection."""
    try:
        data = client_socket.recv(1024).decode('utf-8').strip()
        
        if not data:
            return
        
        log_debug(f"Received: {data}")
        
        try:
            request = json.loads(data)
        except json.JSONDecodeError:
            response = {"status": "error", "message": "Invalid JSON"}
            client_socket.sendall((json.dumps(response) + "\n").encode())
            return
        
        action = request.get('action')
        
        if action == 'launch':
            app_id = request.get('app_id')
            if not app_id:
                response = {"status": "error", "message": "app_id required"}
            else:
                success = launch_app(app_id)
                if success:
                    response = {"status": "ok"}
                else:
                    response = {"status": "error", "message": f"Failed to launch {app_id}"}
        else:
            response = {"status": "error", "message": f"Unknown action: {action}"}
        
        log_debug(f"Sending: {json.dumps(response)}")
        client_socket.sendall((json.dumps(response) + "\n").encode())
        
    except Exception as e:
        log_error(f"Error handling client: {e}")
    finally:
        client_socket.close()

def start_ipc_server():
    """Start the Unix domain socket IPC server."""
    # Clean up old socket
    if os.path.exists(SOCKET_PATH):
        try:
            os.remove(SOCKET_PATH)
        except:
            pass
    
    server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(SOCKET_PATH)
    server_socket.listen(1)
    
    log_info(f"IPC server listening on {SOCKET_PATH}")
    
    return server_socket

# ===== MAIN =====

def daemon_main_loop(server_socket):
    """Main daemon event loop."""
    log_info("Daemon ready, awaiting requests...")
    
    try:
        while True:
            try:
                client_socket, addr = server_socket.accept()
                handle_client(client_socket, addr)
            except KeyboardInterrupt:
                break
            except Exception as e:
                log_error(f"Error in main loop: {e}")
    except KeyboardInterrupt:
        log_info("Received interrupt signal")

def daemon_startup():
    """Initialize daemon on startup."""
    log_info("="*50)
    log_info("Router Daemon Starting")
    log_info("="*50)
    log_info(f"Session ID: {session_id}")
    log_info("")
    
    # Load registry
    if not load_registry():
        log_error("Failed to load app registry")
        return False
    
    # Reset Waydroid
    if not reset_waydroid_data():
        log_error("Failed to reset Waydroid")
        return False
    
    # Create VM overlay
    if not create_vm_overlay():
        log_error("Failed to create VM overlay")
        return False
    
    # Update VM config
    if not update_vm_config():
        log_error("Failed to update VM config")
        return False
    
    # Start VM
    if not start_vm():
        log_error("Failed to start VM")
        return False
    
    # Start Waydroid
    if not start_waydroid():
        log_error("Failed to start Waydroid")
        return False
    
    log_info("All backends initialized successfully")
    log_info("")
    
    return True

def daemon_shutdown():
    """Clean shutdown of daemon."""
    log_info("")
    log_info("="*50)
    log_info("Shutting down...")
    log_info("="*50)
    
    # Stop Waydroid
    stop_waydroid()
    
    # Stop VM
    stop_vm()
    
    # Disable networks
    disable_network("vm")
    disable_network("waydroid")
    
    # Clean up overlay
    cleanup_vm_overlay()
    
    # Remove socket
    if os.path.exists(SOCKET_PATH):
        try:
            os.remove(SOCKET_PATH)
        except:
            pass
    
    log_info("Shutdown complete")

def signal_handler(signum, frame):
    """Handle SIGINT and SIGTERM."""
    raise KeyboardInterrupt()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        if not daemon_startup():
            sys.exit(1)
        
        server_socket = start_ipc_server()
        daemon_main_loop(server_socket)
        
    except KeyboardInterrupt:
        pass
    finally:
        daemon_shutdown()
