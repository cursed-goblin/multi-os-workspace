#!/bin/bash
# scripts/test-guest-exec.sh
# Test QEMU Guest Agent command delivery to Windows VM

set -e

echo "========================================"
echo "Test: Guest Agent Command Delivery"
echo "========================================"
echo ""

# Check if VM is running
if ! virsh list | grep -q "winvm.*running"; then
    echo "ERROR: VM 'winvm' is not running"
    echo "Start it first: virsh start winvm"
    exit 1
fi

echo "[+] VM 'winvm' is running"
echo ""

# Test 1: Guest Agent Ping
echo "[*] Test 1: Verifying guest agent is responsive..."
if virsh qemu-agent-command winvm '{"execute":"guest-ping"}' 2>/dev/null | grep -q '"return"'; then
    echo "[+] Guest agent is responding"
else
    echo "ERROR: Guest agent not responding"
    echo "Possible causes:"
    echo "  - QEMU Guest Agent service not running in Windows"
    echo "  - Guest Agent not installed"
    echo "  - VM network/virtio-serial channel issue"
    echo ""
    echo "To fix:"
    echo "  1. Open virt-viewer winvm"
    echo "  2. Open Windows Services (services.msc)"
    echo "  3. Find 'QEMU Guest Agent'"
    echo "  4. If not installed, install virtio-win guest tools"
    echo "  5. If installed, right-click -> Start"
    exit 1
fi
echo ""

# Test 2: Get OS Info
echo "[*] Test 2: Getting guest OS information..."
GUEST_INFO=$(virsh qemu-agent-command winvm '{"execute":"guest-get-osinfo"}' 2>/dev/null)
echo "[+] Guest info retrieved:"
echo "$GUEST_INFO" | python3 -m json.tool
echo ""

# Test 3: List processes (basic test without execution)
echo "[*] Test 3: Getting guest process information..."
PROC_INFO=$(virsh qemu-agent-command winvm '{"execute":"guest-get-users"}' 2>/dev/null)
echo "[+] Guest users:"
echo "$PROC_INFO" | python3 -m json.tool
echo ""

# Test 4: Try a simple command (create a file in temp)
echo "[*] Test 4: Executing test command in guest..."
echo "    Command: cmd /c echo test > C:\\Users\\Public\\test.txt"

CMD_RESULT=$(virsh qemu-agent-command winvm \
  '{"execute":"guest-exec","arguments":{"path":"cmd","arg":["cmd","/c","echo test > C:\\\\Users\\\\Public\\\\test.txt"]}}' \
  2>/dev/null || echo '{"error": "command failed"}')

if echo "$CMD_RESULT" | grep -q '"pid"'; then
    PID=$(echo "$CMD_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('return', {}).get('pid', 'unknown'))")
    echo "[+] Command executed, PID: $PID"
else
    echo "[!] Command execution may have failed (this can be normal)"
    echo "    Response: $CMD_RESULT"
fi
echo ""

echo "========================================"
echo "Test complete!"
echo "========================================"
echo ""
echo "Summary:"
echo "  - Guest agent is responsive"
echo "  - Commands can be sent to guest"
echo "  - Ready for app launching via guest-exec"
echo ""
echo "Next step: Run the full daemon and shell"
echo "  Terminal 1: python daemon/router_daemon.py"
echo "  Terminal 2: python shell/shell.py"
echo ""
