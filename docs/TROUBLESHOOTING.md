# Troubleshooting Guide

## Common Issues and Solutions

### Host Setup Issues

#### "virsh: cannot connect to libvirtd"

**Problem**: Libvirt daemon not running.

**Solution**:
```bash
sudo systemctl start libvirtd
sudo systemctl enable libvirtd
```

#### "Permission denied" when running virsh commands

**Problem**: User not in `libvirt` group.

**Solution**:
```bash
sudo usermod -aG libvirt $USER
# Log out and back in for group membership to take effect
groups  # Verify libvirt appears in output
```

#### "qemu-system-x86_64: no permission to set high NUMA nodes (>127) check /proc/sys/vm/mmap_min_addr."

**Problem**: QEMU memory mapping issue.

**Solution**:
```bash
sudo sysctl vm.mmap_min_addr=0
# To make permanent, add to /etc/sysctl.d/99-mmap.conf:
# vm.mmap_min_addr=0
```

### Windows VM Issues

#### "virsh: error: Domain not found"

**Problem**: VM named `winvm` does not exist.

**Solution**: Ensure you created the VM with the exact name `winvm` in virt-manager. If you named it differently, either:
1. Edit `daemon/router_daemon.py` and change the VM name constant, or
2. Rename the VM: `virsh rename <old-name> winvm`

#### SPICE window doesn't open when launching Windows app

**Problem**: SPICE display not configured correctly, or `spicy`/`virt-viewer` not installed.

**Solution**:
```bash
# Install SPICE clients
sudo apt-get install virt-viewer spice-client-gtk

# Verify VM has SPICE display
virsh dumpxml winvm | grep spice
# Should show: <graphics type='spice' port=... />

# Manually test SPICE client
virt-viewer winvm
# If this opens a window to the VM, SPICE is working
```

#### Guest Agent not responding

**Problem**: `virsh qemu-agent-command` returns "error: Guest agent not available".

**Solution**:
1. Verify guest agent is installed inside Windows VM
2. Verify it's running: Open Windows Services (services.msc), find "QEMU Guest Agent"
3. If not running, double-click it and click "Start"
4. Reboot the VM

#### Windows VM consumes too much CPU/RAM when idle

**Problem**: Windows Update, Search Indexing, or telemetry running.

**Solution**: In Windows guest:
1. Open Services (services.msc)
2. Set these to "Disabled" and "Stop":
   - Windows Update
   - Windows Search
   - DiagTrack (Diagnostic Tracking)
   - dmwappushservice
   - OneSyncSvc
3. Disable animations in Settings → System → Display
4. Reboot

Verify CPU/RAM usage returns to near-0%.

#### "Can't connect to isolated-net"

**Problem**: Libvirt network `isolated-net` not defined.

**Solution**: Create it:
```bash
cat > /tmp/isolated-net.xml << 'EOF'
<network>
  <name>isolated-net</name>
  <forward mode='nat'>
    <nat>
      <port start='1024' end='65535'/>
    </nat>
  </forward>
  <bridge name='virbr-isolated' stp='on' delay='0'/>
  <ip address='192.168.100.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.100.2' end='192.168.100.254'/>
    </dhcp>
  </ip>
</network>
EOF

virsh net-define /tmp/isolated-net.xml
virsh net-start isolated-net
virsh net-autostart isolated-net
```

### Waydroid Issues

#### "waydroid session start" hangs

**Problem**: Waydroid initialization incomplete or corrupted data.

**Solution**:
```bash
# Stop any running session
waydroid session stop

# Wipe and reinitialize
rm -rf ~/.waydroid
waydroid init

# Start again
waydroid session start
```

#### Android app window doesn't appear on host

**Problem**: Waydroid not properly integrated with Wayland, or app not installed.

**Solution**:
1. Verify app is installed:
   ```bash
   waydroid app list
   ```
2. Try launching manually:
   ```bash
   waydroid session start &
   waydroid app launch <package.name>
   ```
3. If still no window, check if you're on Wayland:
   ```bash
   echo $XDG_SESSION_TYPE
   # Should output "wayland"
   ```
4. If on X11, Waydroid still works but windows may not integrate cleanly (use XWayland, less preferred)

#### Network isolation not working for Waydroid

**Problem**: Android apps can still reach the internet even though firewall rules should block them.

**Solution**:
1. Verify firewall rules are active:
   ```bash
   sudo iptables -L FORWARD -n
   # Or for nftables:
   sudo nft list ruleset
   ```
2. Manually block Waydroid subnet:
   ```bash
   # Find Waydroid subnet
   ip addr show dev waydroid0
   # Should show something like 192.168.240.1/24
   
   # Block it
   sudo iptables -I FORWARD -i waydroid0 -j REJECT
   sudo iptables -I FORWARD -o waydroid0 -j REJECT
   ```

### Router Daemon Issues

#### "[ERROR] Failed to connect to libvirt"

**Problem**: libvirtd not running or user doesn't have permission.

**Solution**: See "Host Setup Issues" section above.

#### "[ERROR] App registry file not found"

**Problem**: `daemon/app_registry.json` doesn't exist.

**Solution**:
```bash
cp daemon/app_registry.json.example daemon/app_registry.json
# Edit it with your apps
```

#### Daemon crashes on startup

**Problem**: Python error or missing dependency.

**Solution**:
```bash
# Check Python version
python3 --version  # Should be 3.10+

# Install dependencies
cd daemon
pip install -r requirements.txt

# Run with verbose output to see error
python3 -u router_daemon.py 2>&1 | head -50
```

#### "Unix socket already in use" error

**Problem**: Previous daemon instance still running or socket file stale.

**Solution**:
```bash
# Kill old daemon
pkill -f router_daemon.py

# Remove stale socket
rm -f /run/user/$(id -u)/router.sock

# Start daemon again
python daemon/router_daemon.py
```

### Shell GUI Issues

#### "[ERROR] Could not connect to daemon socket"

**Problem**: Router Daemon not running, or socket not found.

**Solution**:
1. Verify daemon is running:
   ```bash
   pgrep -f router_daemon.py
   ```
2. If not running, start it:
   ```bash
   python daemon/router_daemon.py &
   ```
3. Verify socket exists:
   ```bash
   ls -l /run/user/$(id -u)/router.sock
   ```

#### Shell window doesn't appear

**Problem**: tkinter not installed or display server issue.

**Solution**:
```bash
# Install tkinter
sudo apt-get install python3-tk

# Verify X11/Wayland
echo $DISPLAY
echo $XDG_SESSION_TYPE

# Run shell with verbose output
python3 -u shell/shell.py 2>&1
```

#### App icons not loading

**Problem**: Icon paths in `app_registry.json` are incorrect or files don't exist.

**Solution**:
1. Verify paths are absolute:
   ```json
   "icon_path": "/usr/share/pixmaps/firefox.png"
   ```
2. Check file exists:
   ```bash
   ls -l /usr/share/pixmaps/firefox.png
   ```
3. Find icon for an app:
   ```bash
   find /usr/share/icons -name "*firefox*" | head -5
   ```

### Network Access Issues

#### Windows app can't reach internet even though `needs_network: true`

**Problem**: Firewall rule added but not correct, or VM network config issue.

**Solution**:
1. Check firewall rules:
   ```bash
   sudo iptables -L FORWARD -v
   # Look for a REJECT rule on 192.168.100.0/24 subnet
   ```
2. Manually test VM network:
   ```bash
   # From inside VM, ping host gateway
   ping 192.168.100.1
   # Then try internet
   ping 8.8.8.8
   ```
3. If still blocked, remove rule and re-add:
   ```bash
   sudo iptables -D FORWARD -i virbr-isolated -j REJECT
   sudo iptables -I FORWARD -i virbr-isolated -j ACCEPT
   ```

#### Android app can't reach internet even though `needs_network: true`

**Problem**: Waydroid network namespace issue or firewall rules.

**Solution**:
1. Check Waydroid network config:
   ```bash
   waydroid status
   # Should show "Session running"
   
   # From inside Waydroid, test connectivity
   waydroid shell ping 8.8.8.8
   ```
2. Manually adjust firewall if needed (see Windows app solution above, but with `waydroid0` interface)

### Session Startup Slow

#### Daemon takes 30+ seconds to start

**Problem**: VM overlay creation or Waydroid data reset taking too long.

**Solution**:
1. Check disk speed:
   ```bash
   # Time overlay creation
   time qemu-img create -f qcow2 -b /var/lib/libvirt/images/winvm-base.qcow2 /tmp/test-overlay.qcow2
   ```
2. If slow, use faster storage (SSD preferred over HDD)
3. Check backup size:
   ```bash
   du -sh /var/lib/waydroid-clean-backup/
   ```
4. If Waydroid backup is large, consider pre-compressing it (advanced optimization)

### Debug Mode

To run components with maximum verbosity:

#### Router Daemon
```bash
# Edit daemon/router_daemon.py, set:
# DEBUG = True
# Then run:
python3 -u daemon/router_daemon.py 2>&1
```

#### Shell
```bash
# Edit shell/shell.py, set:
# DEBUG = True
# Then run:
python3 -u shell/shell.py 2>&1
```

#### VM
```bash
# Get SPICE console directly
virt-viewer winvm

# Or check VM logs
virsh dumpxml winvm
cat /var/log/libvirt/qemu/winvm.log
```

#### Waydroid
```bash
# Check session logs
waydroid log-cat

# Or check system logs
journalctl -u waydroid -n 50
```

### Still Stuck?

1. **Check component-specific logs**:
   ```bash
   journalctl -u router-daemon.service -n 100
   journalctl -u libvirtd -n 100
   ```

2. **Run standalone test scripts** to isolate the problem:
   ```bash
   bash scripts/test-vm-overlay.sh
   bash scripts/test-waydroid-reset.sh
   bash scripts/test-guest-exec.sh
   ```

3. **Enable all debug output** and paste full output to issue tracker

4. **Verify all prerequisites** from SETUP.md are installed
