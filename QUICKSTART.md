# Quick Start Guide

## 5-Minute Setup (After Prerequisites)

Assuming you've completed the full setup in `docs/SETUP.md`, here's the quick start:

### Terminal 1: Start the Router Daemon

```bash
cd /path/to/multi-os-workspace
python3 daemon/router_daemon.py
```

You should see output like:

```
[INFO] ==================================================
[INFO] Router Daemon Starting
[INFO] ==================================================
[INFO] Session ID: abc12345
[INFO] Loaded 5 apps from registry
[INFO] Resetting Waydroid data...
[INFO] Creating Windows VM overlay disk...
[INFO] Updating VM configuration...
[INFO] Starting Windows VM 'winvm'...
[INFO] Starting Waydroid session...
[INFO] All backends initialized successfully
[INFO] IPC server listening on /run/user/1000/router.sock
[INFO] Daemon ready, awaiting requests...
```

**Leave this running in the background.**

### Terminal 2: Start the Shell GUI

```bash
cd /path/to/multi-os-workspace
python3 shell/shell.py
```

The app drawer window should appear with all your configured apps.

### Try It!

Click any app icon to launch it. The first time may take a few seconds as backends initialize.

---

## Common Commands

### Verify Daemon is Running

```bash
pgrep -f router_daemon.py
# Should return a PID
```

### Verify Shell is Running

```bash
pgrep -f shell.py
# Should return a PID
```

### View Daemon Logs

```bash
journalctl -u router-daemon.service -f  # If using systemd
# Or just read the terminal where you started it
```

### Stop Everything (Clean Shutdown)

```bash
# In the daemon terminal, press Ctrl+C
# In the shell terminal, press Ctrl+C or close the window
```

The daemon will automatically:
- Stop Waydroid session
- Stop Windows VM
- Delete VM overlay disk
- Remove firewall rules

### View VM Display

```bash
virt-viewer winvm
```

### View Waydroid Full UI

```bash
waydroid session start &
waydroid show-full-ui
```

### Check Waydroid Apps

```bash
waydroid app list
```

---

## Troubleshooting

### "Could not connect to Router Daemon"

**Problem**: Daemon not running

**Solution**: Start daemon first:
```bash
python3 daemon/router_daemon.py
```

### "No apps configured"

**Problem**: App registry doesn't exist or is empty

**Solution**:
```bash
cp daemon/app_registry.json.example daemon/app_registry.json
# Edit daemon/app_registry.json with your apps
```

### App launch fails

1. Check daemon terminal for error messages
2. Verify the app exists on the target OS
3. Check icon path is correct (absolute path)
4. For Windows apps: verify QEMU Guest Agent is running in VM
5. For Android apps: verify package is installed

See `docs/TROUBLESHOOTING.md` for more.

---

## Next Steps

- **Edit app registry**: `daemon/app_registry.json` — add/remove/customize apps
- **Customize shell**: `shell/shell.py` — adjust colors, fonts, grid layout
- **Enable systemd service**: `systemctl --user enable router-daemon.service`
- **Read architecture**: `docs/ARCHITECTURE.md` — understand how it all works
- **Run tests**: `bash scripts/test-*.sh` — verify each component independently

---

## File Structure Reference

```
multi-os-workspace/
├── README.md                      # Project overview
├── QUICKSTART.md                  # This file
├── docs/
│   ├── SETUP.md                   # Full setup instructions
│   ├── ARCHITECTURE.md            # Technical deep dive
│   └── TROUBLESHOOTING.md         # Common issues
├── setup/
│   ├── install-host-deps.sh       # Install packages (run once)
│   ├── prepare-vm.sh              # VM setup (manual)
│   └── prepare-waydroid.sh        # Waydroid backup (run once)
├── daemon/
│   ├── router_daemon.py           # Main daemon (start first)
│   ├── app_registry.json          # Your app list (edit this)
│   ├── app_registry.json.example  # Template
│   ├── app_registry.schema.json   # Validation schema
│   └── requirements.txt           # Python deps
├── shell/
│   ├── shell.py                   # App drawer GUI (start second)
│   └── requirements.txt           # Python deps
├── scripts/
│   ├── test-vm-overlay.sh         # Test VM boot
│   ├── test-waydroid-reset.sh     # Test Waydroid reset
│   ├── test-guest-exec.sh         # Test guest agent
│   └── window-helper.ps1          # Windows helper (install in VM)
└── systemd/
    └── router-daemon.service      # Auto-start service (optional)
```

---

## Tips & Tricks

### Run Daemon in Background

```bash
python3 daemon/router_daemon.py &
```

### Run Shell Full-Screen

Edit `shell/shell.py` and change:
```python
self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
```
to:
```python
self.root.state('zoomed')  # Windows
# or
self.root.attributes('-zoomed', True)  # Linux
```

### Auto-Start on Login

```bash
mkdir -p ~/.config/systemd/user/
cp systemd/router-daemon.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable router-daemon.service
systemctl --user start router-daemon.service

# Verify
systemctl --user status router-daemon.service
```

### Debug Mode

Edit `daemon/router_daemon.py` or `shell/shell.py` and set:
```python
DEBUG = True
```

Then restart. You'll see detailed logs for every operation.

---

## Have Fun!

You now have a unified desktop that transparently blends Linux, Windows, and Android apps.

For issues or feature requests, see `docs/TROUBLESHOOTING.md` or check the GitHub issues.
