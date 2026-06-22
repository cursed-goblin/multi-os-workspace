# Multi-OS Unified Workspace

A Linux-hosted desktop environment that transparently launches and displays applications from three operating systems (Linux, Windows/Tiny10, Android/Waydroid) as if they were one unified OS.

## Overview

- **Host**: Linux Mint with Wayland compositor
- **Backend A**: Windows 10 (Tiny10) running in QEMU/KVM VM
- **Backend B**: Android running in Waydroid container
- **Router Daemon**: Central process managing backend lifecycle, app launching, and window surfacing
- **Shell**: Lightweight GUI app drawer (tkinter) for launching apps

## Directory Structure

```
multi-os-workspace/
├── README.md                          # This file
├── docs/                              # Documentation
│   ├── SETUP.md                       # Step-by-step setup guide
│   ├── ARCHITECTURE.md                # Detailed architecture
│   └── TROUBLESHOOTING.md             # Common issues and fixes
├── setup/                             # Host environment setup
│   ├── install-host-deps.sh           # Install KVM, libvirt, Waydroid on Linux Mint
│   ├── prepare-vm.sh                  # Tiny10 VM base image preparation (manual)
│   └── prepare-waydroid.sh            # Waydroid data backup script
├── daemon/                            # Router Daemon (Python)
│   ├── router_daemon.py               # Main daemon process
│   ├── app_registry.json              # App registry (edit to add/remove apps)
│   ├── app_registry.schema.json       # Schema for app registry
│   └── requirements.txt               # Python dependencies
├── shell/                             # Shell GUI (tkinter)
│   ├── shell.py                       # Main GUI application
│   └── requirements.txt               # Python dependencies
├── scripts/                           # Standalone test/utility scripts
│   ├── test-vm-overlay.sh             # Test: create VM overlay and boot
│   ├── test-waydroid-reset.sh         # Test: reset Waydroid data and start
│   ├── test-guest-exec.sh             # Test: send command to guest via agent
│   └── window-helper.ps1              # Windows guest helper script (install in Tiny10)
└── systemd/                           # Systemd user service
    └── router-daemon.service          # Service file (install to ~/.config/systemd/user/)
```

## Quick Start

1. **Prepare host**: Run `setup/install-host-deps.sh`
2. **Prepare Windows VM**: Follow `docs/SETUP.md` section 2 (manual—download Tiny10 ISO, create VM, install guest agent)
3. **Prepare Waydroid**: Run `setup/prepare-waydroid.sh` after Waydroid init
4. **Run standalone tests**: Test each component independently (see `scripts/`)
5. **Configure app registry**: Edit `daemon/app_registry.json` with your apps
6. **Start daemon**: `python daemon/router_daemon.py` or enable systemd service
7. **Run shell**: `python shell/shell.py`

## Version

v1 (MVP)

### Intentional v1 Limitations

- One Windows app window visible at a time (VM has single display)
- No persistent user data across sessions
- No GPU passthrough (uses virtio-gpu)
- Single-user, single-session
- Manual app registry maintenance

See `docs/TROUBLESHOOTING.md` for known issues and workarounds.
