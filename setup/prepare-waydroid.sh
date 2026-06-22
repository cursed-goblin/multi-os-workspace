#!/bin/bash
# setup/prepare-waydroid.sh
# Backup clean Waydroid state for session resets

set -e

echo "========================================"
echo "Waydroid State Backup"
echo "========================================"
echo ""

WAYDROID_DATA="/var/lib/waydroid"
WAYDROID_BACKUP="/var/lib/waydroid-clean-backup"

if [ ! -d "$WAYDROID_DATA" ]; then
    echo "ERROR: Waydroid data directory not found at $WAYDROID_DATA"
    echo "Have you run 'waydroid init' yet?"
    exit 1
fi

echo "[*] Waydroid data directory: $WAYDROID_DATA"
echo "[*] Backup destination: $WAYDROID_BACKUP"
echo ""

# Check if Waydroid session is running
if pgrep -f "waydroid.*session" > /dev/null; then
    echo "[!] Waydroid session is currently running"
    echo "[*] Stopping session..."
    waydroid session stop
    sleep 2
fi

# Remove old backup if it exists
if [ -d "$WAYDROID_BACKUP" ]; then
    echo "[*] Removing old backup..."
    sudo rm -rf "$WAYDROID_BACKUP"
fi

# Create backup
echo "[*] Creating backup of clean Waydroid state..."
echo "    This may take a minute (copying ~5-10GB)..."
sudo cp -r "$WAYDROID_DATA" "$WAYDROID_BACKUP"

echo "[*] Setting backup to read-only..."
sudo chmod -R 555 "$WAYDROID_BACKUP"

echo ""
echo "========================================"
echo "Backup complete!"
echo "========================================"
echo ""
echo "Backup size:"
sudo du -sh "$WAYDROID_BACKUP"
echo ""
echo "At session start, the router daemon will:"
echo "  1. Delete current Waydroid data directory"
echo "  2. Restore this backup"
echo "  3. Start a fresh Waydroid session"
echo ""
