#!/bin/bash
# setup/install-host-deps.sh
# Install all required host dependencies for Multi-OS Unified Workspace on Linux Mint

set -e

echo "========================================"
echo "Multi-OS Workspace: Host Dependencies"
echo "========================================"
echo ""

# Detect Linux distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "ERROR: Cannot detect Linux distribution"
    exit 1
fi

echo "[*] Detected OS: $OS"

# Check if running Linux Mint or Ubuntu
if [ "$OS" != "linuxmint" ] && [ "$OS" != "ubuntu" ]; then
    echo "WARNING: This script is designed for Linux Mint/Ubuntu"
    echo "Some package names may differ on other distributions"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update package lists
echo "[*] Updating package lists..."
sudo apt-get update

# Install KVM/QEMU/libvirt
echo "[*] Installing KVM, QEMU, and libvirt..."
sudo apt-get install -y \
    qemu-system-x86 \
    qemu-utils \
    libvirt-daemon-system \
    libvirt-clients \
    virt-manager \
    virt-viewer \
    spice-client-gtk \
    bridge-utils

# Install Waydroid dependencies
echo "[*] Installing Waydroid..."
sudo apt-get install -y \
    waydroid \
    python3-gbulb

# Install NFTABLES or IPTABLES for firewall rules
echo "[*] Installing firewall tools..."
sudo apt-get install -y \
    nftables \
    iptables

# Install Python development tools
echo "[*] Installing Python 3 and pip..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-tk \
    python3-dev

# Install libvirt Python bindings
echo "[*] Installing Python libvirt bindings..."
sudo apt-get install -y libvirt-python3

# Install X11 tools for window management (wmctrl, xdotool)
echo "[*] Installing window management tools..."
sudo apt-get install -y \
    wmctrl \
    xdotool

# Add user to libvirt and kvm groups
echo "[*] Adding $USER to kvm and libvirt groups..."
sudo usermod -aG kvm $USER
sudo usermod -aG libvirt $USER

# Create necessary directories
echo "[*] Creating working directories..."
mkdir -p ~/.config/systemd/user
mkdir -p ~/.cache/multi-os-workspace

# Enable libvirtd service
echo "[*] Enabling libvirtd service..."
sudo systemctl enable libvirtd
sudo systemctl start libvirtd

# Create isolated libvirt network if it doesn't exist
echo "[*] Creating isolated libvirt network..."
if ! virsh net-list | grep -q isolated-net; then
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
    echo "[+] isolated-net created and started"
else
    echo "[+] isolated-net already exists"
fi

echo ""
echo "========================================"
echo "Installation complete!"
echo "========================================"
echo ""
echo "IMPORTANT: Log out and back in to apply group membership changes"
echo "Run: newgrp kvm && newgrp libvirt"
echo "Or simply log out and back in"
echo ""
echo "Verify installation with:"
echo "  virt-host-validate qemu"
echo "  waydroid status"
echo ""
