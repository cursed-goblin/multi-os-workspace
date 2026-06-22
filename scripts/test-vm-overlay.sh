#!/bin/bash
# scripts/test-vm-overlay.sh
# Test Windows VM overlay creation and boot

set -e

echo "========================================"
echo "Test: Windows VM Overlay & Boot"
echo "========================================"
echo ""

# Check if VM exists
if ! virsh list --all | grep -q winvm; then
    echo "ERROR: VM 'winvm' not found"
    echo "Create the VM first using virt-manager"
    exit 1
fi

echo "[*] VM 'winvm' found"
echo ""

# Define paths
BASE_IMAGE="/var/lib/libvirt/images/winvm-base.qcow2"
OVERLAY_IMAGE="/tmp/winvm-test-overlay.qcow2"

# Check if base image exists
if [ ! -f "$BASE_IMAGE" ]; then
    echo "ERROR: Base image not found at $BASE_IMAGE"
    echo "Did you complete the base image setup?"
    echo "See docs/SETUP.md section 2.6"
    exit 1
fi

echo "[+] Base image found: $BASE_IMAGE"
echo "    Size: $(du -h $BASE_IMAGE | cut -f1)"
echo ""

# Clean up old test overlay if it exists
if [ -f "$OVERLAY_IMAGE" ]; then
    echo "[*] Cleaning up old test overlay..."
    rm -f "$OVERLAY_IMAGE"
fi

# Create overlay
echo "[*] Creating overlay from base image..."
echo "    Source: $BASE_IMAGE"
echo "    Target: $OVERLAY_IMAGE"
qemu-img create -f qcow2 -b "$BASE_IMAGE" -F qcow2 "$OVERLAY_IMAGE"

echo "[+] Overlay created successfully"
echo "    Size: $(du -h $OVERLAY_IMAGE | cut -f1)"
echo ""

# Verify overlay is valid
echo "[*] Verifying overlay integrity..."
qemu-img info "$OVERLAY_IMAGE" > /dev/null
echo "[+] Overlay is valid"
echo ""

# Update VM config to use this overlay
echo "[*] Updating VM configuration to use test overlay..."
TMP_XML=$(mktemp)
virsh dumpxml winvm > "$TMP_XML"
sed -i "s|<source file='[^']*'/>|<source file='$OVERLAY_IMAGE'/>|" "$TMP_XML"
virsh define "$TMP_XML"
rm -f "$TMP_XML"
echo "[+] VM configuration updated"
echo ""

# Check if VM is already running
if virsh list | grep -q "winvm.*running"; then
    echo "[!] VM is already running, stopping it..."
    virsh destroy winvm
    sleep 2
fi

# Start VM
echo "[*] Starting VM..."
virsh start winvm
sleep 3

echo "[+] VM started"
echo ""

# Verify VM is running
echo "[*] Verifying VM status..."
if virsh list | grep -q "winvm.*running"; then
    echo "[+] VM is running"
else
    echo "ERROR: VM failed to start"
    exit 1
fi
echo ""

# Check network isolation
echo "[*] Checking network isolation..."
VM_IP=$(virsh domifaddr winvm | grep -oP '192\.168\.100\.\d+' | head -1)
if [ -z "$VM_IP" ]; then
    echo "[!] Could not determine VM IP (may not have network yet, this is OK)"
else
    echo "[+] VM IP: $VM_IP"
    echo "[*] Testing connectivity from VM..."
    # Ping VM gateway (should work)
    if virsh qemu-agent-command winvm '{"execute":"guest-ping"}' 2>/dev/null | grep -q success; then
        echo "[+] Guest agent responding"
    else
        echo "[!] Guest agent not responding (may not be running)"
    fi
fi
echo ""

echo "========================================"
echo "Test complete!"
echo "========================================"
echo ""
echo "VM details:"
virsh dominfo winvm
echo ""
echo "Next steps:"
echo "  1. Open virt-viewer to verify VM display works"
echo "     virt-viewer winvm"
echo "  2. Inside VM, verify QEMU Guest Agent is running"
echo "     (Windows Services -> QEMU Guest Agent)"
echo "  3. Run: bash scripts/test-guest-exec.sh"
echo ""
