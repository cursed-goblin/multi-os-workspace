# C:\runner.ps1
# Windows Guest Helper Script
# Installed at C:\runner.ps1 during Tiny10 setup
# Called by Router Daemon to launch apps and maximize their windows
#
# Usage: powershell.exe C:\runner.ps1 "C:\\Path\\To\\App.exe"

Param(
    [string]$AppPath = $(throw "App path required"),
    [int]$MaxWaitSeconds = 5
)

# Enable error handling
$ErrorActionPreference = "Continue"

# Helper function: Get window handle by process
function Get-WindowHandle {
    param([System.Diagnostics.Process]$Process)
    
    $timeout = [datetime]::Now.AddSeconds(2)
    while ([datetime]::Now -lt $timeout) {
        if ($Process.MainWindowHandle -ne 0) {
            return $Process.MainWindowHandle
        }
        Start-Sleep -Milliseconds 100
    }
    return 0
}

# Win32 API declarations
Add-Type @"
using System;
using System.Runtime.InteropServices;

public class WinAPI {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    
    // Window display modes
    public const int SW_HIDE = 0;
    public const int SW_MAXIMIZE = 3;
    public const int SW_SHOW = 5;
}
"@

# Function to hide taskbar
function Hide-Taskbar {
    try {
        $taskbar = [WinAPI]::FindWindow("Shell_traywnd", [System.String]::Empty)
        if ($taskbar -ne [IntPtr]::Zero) {
            [WinAPI]::ShowWindow($taskbar, [WinAPI]::SW_HIDE) | Out-Null
        }
    } catch {
        # Non-critical if taskbar hiding fails
    }
}

# Function to maximize foreground window
function Maximize-Window {
    try {
        $foreground = [WinAPI]::GetForegroundWindow()
        if ($foreground -ne [IntPtr]::Zero) {
            [WinAPI]::ShowWindow($foreground, [WinAPI]::SW_MAXIMIZE) | Out-Null
        }
    } catch {
        # Non-critical if maximize fails
    }
}

# Main execution
try {
    Write-Host "[*] Launching application: $AppPath"
    
    # Start the process
    $process = Start-Process -FilePath $AppPath -PassThru -ErrorAction Stop
    $pid = $process.Id
    
    Write-Host "[+] Process started with PID: $pid"
    
    # Wait for window to appear
    Write-Host "[*] Waiting for window to appear..."
    Start-Sleep -Milliseconds 500
    
    # Hide taskbar (best effort)
    Write-Host "[*] Hiding taskbar..."
    Hide-Taskbar
    
    # Maximize the app window
    Write-Host "[*] Maximizing application window..."
    Maximize-Window
    
    Write-Host "[+] Application launched and configured"
    Write-Host "[*] Bringing window to foreground..."
    
    # Try to bring window to foreground
    $hWnd = $process.MainWindowHandle
    if ($hWnd -ne 0) {
        [WinAPI]::SetForegroundWindow($hWnd) | Out-Null
    }
    
    Write-Host "[+] Done!"
    
} catch {
    Write-Error "Failed to launch application: $_"
    exit 1
}

# Keep script alive briefly to ensure window setup completes
Start-Sleep -Milliseconds 500
exit 0
