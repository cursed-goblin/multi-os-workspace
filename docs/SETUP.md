# Setup Guide: Multi-OS Unified Workspace

This guide walks through setting up the entire system from scratch on Linux Mint.

## Prerequisites

- Linux Mint 21.3+ (using Cinnamon or MATE with Wayland support, or switch to Wayland session)
- At least 60GB free disk space (40GB for Windows VM, 10GB for Android, 10GB buffer)
- At least 8GB RAM (4GB host + 2GB Windows VM + 2GB Android/buffer)
- Internet connection for downloading ISOs and packages

## Phase 1: Host Environment Setup (Automated)

### 1.1 Install Host Dependencies

```bash
bash setup/install-host-deps.sh
```

This script will:
- Install KVM, QEMU, libvirt, virt-manager
- Add your user to `kvm` and `libvirt` groups
- Install Waydroid and dependencies
- Install Python 3.10+ and pip
- Create necessary directories

**After running, log out and back in** to pick up group membership changes.

Verify:
```bash
virt-host-validate qemu
waydroid status
```

### 1.2 Enable Wayland (if using GNOME/Wayland-capable session)

If on Cinnamon, skip this—Cinnamon uses X11 with XWayland, which works fine with Waydroid.

If on GNOME:
1. Log out
2. At login screen, click your username, then select "GNOME on Wayland" from the session dropdown
3. Log back in

## Phase 2: Windows VM Preparation (Manual)

This requires user intervention with GUI tools.

### 2.1 Obtain Tiny10 ISO

1. Download a Tiny10 ISO from a trusted source (e.g., the official Tiny10 GitHub releases)
2. Verify the SHA hash if provided
3. Save to a known location, e.g., `~/Downloads/tiny10.iso`

**⚠️ NOTE**: This project does NOT distribute Windows ISOs. You must obtain Tiny10 legally yourself.

### 2.2 Create Windows VM with virt-manager

1. Open **Virtual Machine Manager** (or run `virt-manager` from terminal)
2. Click **Create a new virtual machine**
3. Choose **Local install media (ISO image or CDROM)**
4. Select the Tiny10 ISO you downloaded
5. Configure:
   - **Name**: `winvm`
   - **RAM**: 2048 MB (2GB)
   - **vCPUs**: 2
   - **Disk**: Create new image → 40 GB, QEMU qcow2 format
6. Click **Customize configuration before install**
7. In the configuration window:
   - Go to **Display** section → set Display type to **SPICE**
   - Go to **Add Hardware** → Network → Select **isolated-net** (if it doesn't exist, see 2.4)
   - Remove the default NAT network if present
   - Apply and close
8. Begin installation
9. Follow the Tiny10 installer normally
10. Once Tiny10 is installed and boots, log in

### 2.3 Install QEMU Guest Agent inside Windows VM

While the VM is running:

1. In virt-manager, click the VM and select **View → Redirect USB device**
2. Download the `virtio-win` ISO on your Linux host:
   ```bash
   cd ~/Downloads
   wget https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/latest/virtio-win.iso
   ```
3. In virt-manager, go to the VM's **Add Hardware** → **Storage** → **CDROM device**
   - Attach the `virtio-win.iso`
4. Inside the Windows guest, open **File Explorer** and double-click the virtio-win CD
5. Run the installer for **QEMU Guest Agent** (or look for `qemu-ga-x86_64.msi`)
6. Complete the installation; the service will start automatically
7. Verify in Windows **Services** (search "services.msc") that "QEMU Guest Agent" is running

### 2.4 Disable Windows Update and Bloat

Inside the Windows guest:

1. Open **Services** (search "services.msc")
2. Disable the following services (set to "Disabled"):
   - Windows Update
   - Windows Search
   - Diagnostic Tracking Service
   - dmwappushservice
   - OneSyncSvc
3. Open **Settings** → **System** → **About** → **Advanced system settings**
   - Go to **Performance** → **Settings** → visual effects → select "Adjust for best performance"
4. Restart

### 2.5 Install Test App (Optional but Recommended)

Install a simple app for testing, e.g., **Notepad++** or **7-Zip**. This will help verify the app-launch mechanism later.

### 2.6 Create VM Base Image and Overlay Structure

Shut down the Windows VM cleanly:
```bash
virsh shutdown winvm
```

Wait for it to power off. Then, on the host:

```bash
# Find the VM's qcow2 disk
VIRSH_LIST=$(virsh domblklist winvm)
echo "$VIRSH_LIST"
# It should show a path like /var/lib/libvirt/images/winvm.qcow2

# Create a read-only base image
BASE_PATH="/var/lib/libvirt/images/winvm-base.qcow2"
WORK_PATH="/var/lib/libvirt/images/winvm.qcow2"

sudo cp "$WORK_PATH" "$BASE_PATH"
sudo chmod 444 "$BASE_PATH"  # Read-only

# Delete the old working copy (it will be recreated as an overlay per session)
sudo rm "$WORK_PATH"
```

Then edit the VM config to point to a new overlay:
```bash
virsh edit winvm
```

Find the `<disk>` section and change the source path to point to a temporary overlay (we'll regenerate it at session start):
```xml
<disk type='file' device='disk'>
  <driver name='qemu' type='qcow2'/>
  <source file='/tmp/winvm-overlay.qcow2'/>
  <target dev='vda' bus='virtio'/>
</disk>
```

Save and close.

### 2.7 Install Window Helper Script (Windows Guest)

On the Windows guest, create a helper script at `C:\runner.ps1`:

```powershell
# C:\runner.ps1
Param([string]$AppPath)

# Launch the app
Start-Process -FilePath $AppPath -NoNewWindow

# Give it a moment to open
Start-Sleep -Milliseconds 500

# Hide taskbar and maximize app
Add-Type @"
using System;
using System.Runtime.InteropServices;

public class WinAPI {
    [DllImport("user32.dll")]
    public static extern IntPtr FindWindow(string className, string windowName);
    
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
}
"@

# Hide the taskbar
$taskbar = [WinAPI]::FindWindow("Shell_traywnd", "")
if ($taskbar -ne [IntPtr]::Zero) {
    [WinAPI]::ShowWindow($taskbar, 0)  # SW_HIDE
}

# Maximize the foreground window (the app)
Start-Sleep -Milliseconds 200
$app = [WinAPI]::GetForegroundWindow()
if ($app -ne [IntPtr]::Zero) {
    [WinAPI]::ShowWindow($app, 3)  # SW_MAXIMIZE
}
```

Then run this in PowerShell (as admin) to allow execution:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Phase 3: Waydroid Preparation (Automated)

### 3.1 Initialize Waydroid

On your Linux host:

```bash
waydroid init
```

When prompted, choose the default (Android 11 or latest stable). This will download several GB; be patient.

Start and verify:
```bash
waydroid session start &
sleep 5
waydroid show-full-ui
```

The Android UI should appear. Close it when satisfied (Ctrl+C in the terminal).

### 3.2 Install Android Apps

While a session is running:

```bash
waydroid session start &

# Install apps via APK files
waydroid app install /path/to/app.apk

# Or, if you enabled Play Store in Waydroid, open it via:
waydroid show-full-ui
# Then use Play Store to install apps

# List installed apps
waydroid app list
```

Note down the package names (e.g., `com.spotify.music`) for later.

### 3.3 Backup Clean Waydroid State

```bash
bash setup/prepare-waydroid.sh
```

This script backs up Waydroid's current state so it can be restored fresh at every session start.

## Phase 4: Build Python Components

### 4.1 Install Router Daemon Dependencies

```bash
cd daemon
pip install -r requirements.txt
cd ..
```

### 4.2 Install Shell Dependencies

```bash
cd shell
pip install -r requirements.txt
cd ..
```

### 4.3 Configure App Registry

Edit `daemon/app_registry.json` and add your apps. See the template for format.

```bash
cp daemon/app_registry.json.example daemon/app_registry.json
# Then edit daemon/app_registry.json with your apps
```

## Phase 5: Test Standalone Scripts

Before running the full system, test each component independently:

### 5.1 Test VM Overlay and Boot

```bash
bash scripts/test-vm-overlay.sh
```

This should:
- Create an overlay disk from the base image
- Start the VM
- Confirm it's running
- Print VM details

### 5.2 Test Waydroid Reset

```bash
bash scripts/test-waydroid-reset.sh
```

This should:
- Reset Waydroid data from backup
- Start a Waydroid session
- List installed apps

### 5.3 Test Guest Exec

```bash
bash scripts/test-guest-exec.sh
```

This should:
- Verify the VM is running
- Send a test command to the guest agent
- Confirm the guest agent responds

## Phase 6: Start the System

### 6.1 Run the Router Daemon

```bash
python daemon/router_daemon.py
```

You should see output like:
```
[INFO] Router Daemon starting...
[INFO] Resetting Waydroid...
[INFO] Creating Windows VM overlay...
[INFO] Starting Windows VM...
[INFO] Starting Waydroid...
[INFO] Listening on /run/user/<uid>/router.sock
```

Leave this running.

### 6.2 In Another Terminal, Run the Shell

```bash
python shell/shell.py
```

The app drawer GUI should appear. Click any app icon to launch it.

### 6.3 (Optional) Enable as Systemd User Service

To start automatically at login:

```bash
mkdir -p ~/.config/systemd/user/
cp systemd/router-daemon.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable router-daemon.service
systemctl --user start router-daemon.service

# Verify
systemctl --user status router-daemon.service
```

## Troubleshooting

See `docs/TROUBLESHOOTING.md` for common issues.
