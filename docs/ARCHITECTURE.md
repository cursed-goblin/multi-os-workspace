# Architecture: Multi-OS Unified Workspace

Detailed technical breakdown of all five components.

## Component 1: Host Linux Environment

**What it is**: The base operating system and display server.

**Role**: Provides KVM virtualization, Wayland compositor, libvirt VM management, and Waydroid container support.

**Technology**:
- Linux Mint with Wayland session (or X11 with XWayland, less preferred but works)
- QEMU/KVM for VM virtualization
- libvirt for VM lifecycle management
- Waydroid for Android containerization

**Key files**:
- `setup/install-host-deps.sh` — installs all required packages

## Component 2: Windows VM (Tiny10)

**What it is**: A minimal Windows 10 virtual machine running under QEMU/KVM.

**Role**: Runs Windows applications in isolation. Always pre-booted and idle so app launch feels instant.

**Key mechanisms**:

### Network Isolation
- VM attached to a private libvirt network (e.g., `192.168.100.0/24`)
- Host-side firewall rules block internet access by default
- Router Daemon opens firewall rules only when an app that needs network is launched
- Mechanism: `nft` or `iptables` rules added/removed by daemon

### Disk Snapshot Pattern
- Base image: read-only `winvm-base.qcow2` (created once during setup)
- Per-session overlay: `winvm-overlay-<sessionid>.qcow2` (created fresh, deleted on logout)
- Ensures every session starts from clean state

### App Launching
- Router Daemon sends JSON-RPC command to QEMU Guest Agent (via virtio-serial channel)
- Guest Agent executes the app inside the VM
- Guest Agent is NOT network-dependent (uses local virtio-serial channel)

### Window Surfacing (Section 5b mechanism)
1. App launches inside VM
2. Helper script (PowerShell) maximizes the app and hides taskbar/other windows
3. Router Daemon opens SPICE client on host pointing to VM's display
4. SPICE client window is borderless, fullscreen-content mode
5. To user, appears as a normal Linux window (app icon, app title, taskbar entry)

**Key files**:
- `scripts/test-vm-overlay.sh` — test overlay creation and VM boot
- `scripts/test-guest-exec.sh` — test guest-agent command delivery
- `scripts/window-helper.ps1` — Windows guest helper script

## Component 3: Android Container (Waydroid)

**What it is**: An Android 11+ container running on the same Linux kernel as the host.

**Role**: Runs Android applications in isolation. Pre-booted and idle so app launch feels instant.

**Key mechanisms**:

### Network Isolation
- Waydroid creates its own virtual interface (e.g., `waydroid0` with subnet `192.168.240.0/24`)
- Host firewall rules block internet by default (same as Windows VM)
- Router Daemon opens rules only when an app that needs network is launched

### Snapshot Pattern
- Waydroid's writable data directory: `/var/lib/waydroid/`
- During setup, backed up to read-only snapshot: `/var/lib/waydroid-clean-backup/`
- At session start, backup is restored, ensuring clean state
- Mechanism: `cp -r` or `rsync` with `--delete` option

### Native Window Integration
- Waydroid integrates natively with Wayland compositor
- When `waydroid app launch <package>` is called, the app window appears directly on host desktop
- NO cropping or remote-display trick needed (unlike Windows)
- This is one of Waydroid's main advantages over VM approaches

**Key files**:
- `setup/prepare-waydroid.sh` — backs up Waydroid state at setup
- `scripts/test-waydroid-reset.sh` — test data reset and session start

## Component 4: Router Daemon

**What it is**: A single long-running Python process managing all backend lifecycle, app launching, and window surfacing.

**Role**: The "brain" of the system. Owns all business logic about which app belongs to which OS, network access rules, and window presentation.

**Architecture**:

### On Startup
1. Read App Registry from JSON file into memory
2. Reset Waydroid data from backup
3. Create fresh Windows VM overlay disk
4. Start Windows VM (headless, no SPICE window yet)
5. Start Waydroid session (no full UI)
6. Open Unix domain socket (IPC endpoint for Shell)
7. Enter main loop: await launch requests

### On App Launch Request
1. Look up app in registry by ID
2. Check app's backend and network requirements
3. If network needed and not yet enabled: add firewall rule
4. Execute appropriate backend-specific launch sequence:
   - **Linux**: `subprocess.run(launch_target)`
   - **Android**: `subprocess.run(["waydroid", "app", "launch", launch_target])`
   - **Windows**: Full Section 5b sequence (guest-exec, helper script, SPICE window)
5. Return success/error to Shell via IPC

### On Shutdown
1. Stop Waydroid session
2. Stop Windows VM
3. Delete Windows VM overlay disk
4. Restore network isolation (remove firewall rules)

**Key files**:
- `daemon/router_daemon.py` — main daemon code
- `daemon/app_registry.json` — app registry (user-editable)
- `daemon/requirements.txt` — Python dependencies (libvirt-python, etc.)

## Component 5: Shell (App Drawer)

**What it is**: A lightweight GUI application listing all apps from all OSes.

**Role**: User-facing interface. Sends "launch this app" requests to Router Daemon. No backend knowledge.

**Architecture**:

### On Startup
1. Connect to Router Daemon's Unix domain socket
2. Read App Registry from JSON file (same file daemon uses)
3. Build UI grid: one icon per app (icon image + display name)
4. Display in fullscreen or windowed mode (configurable)

### On App Click
1. Send `{"action": "launch", "app_id": "..."}` via socket
2. Show loading spinner immediately (don't wait for response)
3. Await response from daemon (confirmation or error)
4. If error, show notification to user

### Design Philosophy
- **Zero backend knowledge**: Shell never asks "is this app Windows or Linux?"
- **Thin client**: All logic lives in Router Daemon
- **Minimal UI**: Just app drawer, no window management, no OS selection

**Technology**:
- Python 3.10+
- tkinter (lightest GUI framework, standard library)
- No external GUI dependencies

**Key files**:
- `shell/shell.py` — main GUI application
- `shell/requirements.txt` — Python dependencies (minimal)

## IPC Protocol: Shell ↔ Router Daemon

**Transport**: Unix domain socket at `/run/user/<uid>/router.sock`

**Format**: Newline-delimited JSON

**Request** (Shell → Daemon):
```json
{"action": "launch", "app_id": "spotify"}
```

**Response** (Daemon → Shell):
```json
{"status": "ok"}
```
or
```json
{"status": "error", "message": "Windows VM not running"}
```

**Future Extensions** (v2+):
- `action: "list_apps"` — query all apps and their status
- `action: "close_app"` — force-close a running app
- `action: "get_status"` — daemon health check

## Execution Flow: Launching an App

### Example 1: Linux App (Firefox)

```
User clicks Firefox icon in Shell
    ↓
Shell sends: {"action": "launch", "app_id": "firefox"}
    ↓
Router Daemon receives, looks up "firefox" in registry
    ↓
Daemon sees backend="linux", launch_target="firefox"
    ↓
Daemon calls: subprocess.run(["firefox"])
    ↓
Firefox starts, window appears on host desktop
    ↓
Daemon responds: {"status": "ok"}
    ↓
Shell hides loading spinner
Done!
```

### Example 2: Android App (Spotify)

```
User clicks Spotify icon in Shell
    ↓
Shell sends: {"action": "launch", "app_id": "spotify"}
    ↓
Router Daemon receives, looks up "spotify" in registry
    ↓
Daemon sees backend="android", launch_target="com.spotify.music", needs_network=true
    ↓
Daemon adds firewall rule to allow waydroid0 subnet to internet
    ↓
Daemon calls: subprocess.run(["waydroid", "app", "launch", "com.spotify.music"])
    ↓
Spotify window appears natively on host desktop (Waydroid integration)
    ↓
Daemon responds: {"status": "ok"}
    ↓
Shell hides loading spinner
Done!
```

### Example 3: Windows App (7-Zip)

```
User clicks 7-Zip icon in Shell
    ↓
Shell sends: {"action": "launch", "app_id": "7zip"}
    ↓
Router Daemon receives, looks up "7zip" in registry
    ↓
Daemon sees backend="windows", launch_target="C:\\Program Files\\7-Zip\\7zFM.exe", needs_network=false
    ↓
Daemon calls guest-exec to launch app via QEMU Guest Agent
    ↓
Guest Agent executes: C:\runner.ps1 "C:\\Program Files\\7-Zip\\7zFM.exe"
    ↓
Helper script launches 7-Zip, hides taskbar, maximizes window
    ↓
Daemon opens SPICE client window (borderless, fullscreen-content)
    ↓
SPICE client window appears on host desktop (appears as 7-Zip app)
    ↓
Daemon responds: {"status": "ok"}
    ↓
Shell hides loading spinner
Done!
```

## Known Limitations (v1)

### One Windows App at a Time
- The Windows VM has a single SPICE display
- Can only show one maximized app window per VM
- Workaround for v2: run multiple Windows VMs or implement Looking Glass multi-window support

### No Persistent User Data
- Every session starts from snapshot
- App settings/downloads are lost on logout
- Workaround: implement persistent home directory mapped to host for v2

### No GPU Passthrough
- Uses virtio-gpu (software rendering)
- Fine for non-3D apps, light/medium games
- Workaround for v2: implement GPU passthrough or Looking Glass

### Single User, Single Session
- No multi-user support
- Cannot have multiple users logged in simultaneously
- Out of scope for v1

## Security Considerations

### Network Isolation
- **By default**: Windows VM and Waydroid have zero internet access
- **Explicit opt-in**: Apps that need network must be marked `needs_network: true` in registry
- **Audit trail**: Firewall rules added by daemon are host-visible (use `iptables -L` or `nft list ruleset`)

### App Confinement
- Windows apps confined to Windows VM (can't escape to host)
- Android apps confined to Waydroid container (can't escape to host)
- Linux apps run natively (no sandboxing in v1, but can be added via flatpak/apparmor in v2)

### Session Isolation
- Every session gets fresh VM and Waydroid overlays
- No data leakage between sessions
- VM overlay deleted on logout

## Performance Notes

### Latencies
- **Linux app launch**: instant (same as any Linux app)
- **Android app launch**: ~1-2 seconds (container already running, app cold-start)
- **Windows app launch**: ~2-4 seconds (QEMU guest-exec roundtrip + app cold-start + SPICE window open)

### Memory Usage
- **Host**: 2-3 GB (compositor, shell, system)
- **Windows VM idle**: 1.5 GB (allocated 2 GB, ballooning returns unused)
- **Waydroid idle**: 0.5-1 GB
- **Total**: 4-5.5 GB idle (within 8GB requirement)

### Disk I/O
- **VM overlay creation**: ~1-2 seconds (qemu-img create)
- **Waydroid reset**: ~1-2 seconds (cp -r from backup)
- **Session start total**: ~5-10 seconds

## Testing Strategy

Test components independently before integration:

1. **test-vm-overlay.sh**: VM overlay creation, boot, network isolation
2. **test-waydroid-reset.sh**: Waydroid data reset, session start
3. **test-guest-exec.sh**: Guest agent command delivery
4. **Manual**: Launch one app from each OS, verify window appearance and functionality
