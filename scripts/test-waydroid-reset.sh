#!/bin/bash
# scripts/test-waydroid-reset.sh
# Test Waydroid data reset and session start

set -e

echo "========================================"
echo "Test: Waydroid Data Reset & Session Start"
echo "========================================"
echo ""

WAYDROID_DATA="/var/lib/waydroid"
WAYDROID_BACKUP="/var/lib/waydroid-clean-backup"

# Check if backup exists
if [ ! -d "$WAYDROID_BACKUP" ]; then
    echo "ERROR: Backup not found at $WAYDROID_BACKUP"
    echo "Run: bash setup/prepare-waydroid.sh"
    exit 1
fi

echo "[+] Backup found: $WAYDROID_BACKUP"
echo ""

# Stop any running session
if pgrep -f "waydroid.*session" > /dev/null; then
    echo "[*] Stopping existing Waydroid session..."
    waydroid session stop
    sleep 2
fi

echo "[*] Resetting Waydroid data directory..."
echo "    Deleting: $WAYDROID_DATA"
sudo rm -rf "$WAYDROID_DATA"

echo "[*] Restoring from backup..."
sudo cp -r "$WAYDROID_BACKUP" "$WAYDROID_DATA"

echo "[+] Waydroid data reset complete"
echo ""

# Start session
echo "[*] Starting Waydroid session..."
waydroid session start
sleep 5

echo "[+] Waydroid session started"
echo ""

# Verify session
echo "[*] Verifying session..."
if waydroid status | grep -q "Session running"; then
    echo "[+] Session is running"
else
    echo "ERROR: Session failed to start"
    exit 1
fi
echo ""

# List installed apps
echo "[*] Listing installed apps..."
echo ""
waydroid app list
echo ""

echo "========================================"
echo "Test complete!"
echo "========================================"
echo ""
echo "Waydroid status:"
waydroid status
echo ""
echo "Next steps:"
echo "  1. Try launching an app: waydroid app launch <package.name>"
echo "  2. Verify the app window appears on your desktop"
echo "  3. Run: bash scripts/test-guest-exec.sh"
echo ""
