"""
Device Fingerprint Security System for Trivox AI Models

Generates a unique hardware fingerprint based on:
  - CPU ID / processor info
  - Motherboard serial (Windows WMI)
  - MAC address
  - Disk serial number
  - Machine name + OS info

The fingerprint is a SHA-256 hash of combined hardware identifiers.
It locks the application to a specific machine so license keys
cannot be transferred without authorization.
"""

import hashlib
import json
import os
import platform
import subprocess
import uuid
from pathlib import Path
from typing import Optional

# Where we cache the fingerprint (avoids re-computing on each launch)
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
FP_CACHE_FILE = CONFIG_DIR / "device_fp.json"


def _run_wmic(alias: str, field: str) -> str:
    """Run a WMIC command and return the first non-empty line."""
    try:
        result = subprocess.run(
            ["wmic", alias, "get", field, "/value"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if "=" in line:
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def _get_cpu_id() -> str:
    """Get CPU processor ID (unique per physical CPU)."""
    if platform.system() == "Windows":
        return _run_wmic("cpu", "ProcessorId")
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "Serial" in line or "model name" in line:
                    return line.split(":")[-1].strip()
    except Exception:
        pass
    return platform.processor()


def _get_motherboard_serial() -> str:
    """Get motherboard serial number (Windows only)."""
    if platform.system() == "Windows":
        return _run_wmic("baseboard", "SerialNumber")
    # Linux fallback
    try:
        with open("/sys/class/dmi/id/board_serial") as f:
            return f.read().strip()
    except Exception:
        return ""


def _get_disk_serial() -> str:
    """Get primary disk serial number."""
    if platform.system() == "Windows":
        return _run_wmic("diskdrive", "SerialNumber")
    try:
        result = subprocess.run(
            ["lsblk", "-dno", "SERIAL"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if line.strip():
                return line.strip()
    except Exception:
        pass
    return ""


def _get_mac_address() -> str:
    """Get the primary MAC address."""
    mac = uuid.getnode()
    return ":".join(f"{(mac >> i) & 0xff:02x}" for i in range(40, -1, -8))


def _get_bios_serial() -> str:
    """Get BIOS serial number (Windows only)."""
    if platform.system() == "Windows":
        return _run_wmic("bios", "SerialNumber")
    return ""


def _get_machine_guid() -> str:
    """Get Windows Machine GUID from registry."""
    if platform.system() != "Windows":
        return ""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return value
    except Exception:
        return ""


def generate_device_fingerprint() -> dict:
    """
    Generate a comprehensive device fingerprint.
    
    Returns a dict with:
      - fingerprint: SHA-256 hash string
      - components: dict of individual hardware identifiers
      - platform: OS info
    """
    components = {
        "cpu_id": _get_cpu_id(),
        "motherboard_serial": _get_motherboard_serial(),
        "disk_serial": _get_disk_serial(),
        "mac_address": _get_mac_address(),
        "bios_serial": _get_bios_serial(),
        "machine_guid": _get_machine_guid(),
        "machine_name": platform.node(),
    }

    # Build a stable string from all components
    # Use sorted keys for consistency
    stable_string = "|".join(
        f"{k}={v}" for k, v in sorted(components.items()) if v
    )

    # SHA-256 hash
    fingerprint = hashlib.sha256(stable_string.encode("utf-8")).hexdigest()

    return {
        "fingerprint": fingerprint,
        "components": components,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }


def get_device_fingerprint() -> str:
    """
    Get or generate+cache the device fingerprint.
    Returns the SHA-256 hash string.
    """
    # Check cache first
    if FP_CACHE_FILE.exists():
        try:
            with open(FP_CACHE_FILE, "r") as f:
                cached = json.load(f)
            if cached.get("fingerprint"):
                # Verify it's still valid (regenerate and compare)
                current = generate_device_fingerprint()
                if current["fingerprint"] == cached["fingerprint"]:
                    return cached["fingerprint"]
                # Hardware changed — update cache
                _save_cache(current)
                return current["fingerprint"]
        except Exception:
            pass

    # Generate fresh
    fp_data = generate_device_fingerprint()
    _save_cache(fp_data)
    return fp_data["fingerprint"]


def get_device_fingerprint_short() -> str:
    """Get a shortened (first 16 chars) fingerprint for display."""
    fp = get_device_fingerprint()
    return fp[:16].upper()


def _save_cache(fp_data: dict) -> None:
    """Save fingerprint to cache file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(FP_CACHE_FILE, "w") as f:
        json.dump(fp_data, f, indent=2)


def verify_device_fingerprint(stored_fp: str) -> bool:
    """
    Verify that the current device matches a stored fingerprint.
    Returns True if they match.
    """
    current = get_device_fingerprint()
    return current == stored_fp


def get_device_info_display() -> str:
    """Get a human-readable device info string for display in UI."""
    fp_data = generate_device_fingerprint()
    comp = fp_data["components"]
    lines = [
        f"Device ID: {fp_data['fingerprint'][:16].upper()}",
        f"Machine: {comp.get('machine_name', 'Unknown')}",
        f"Platform: {fp_data['platform']}",
        f"CPU: {comp.get('cpu_id', 'Unknown')[:20]}",
        f"MAC: {comp.get('mac_address', 'Unknown')}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print("=== Device Fingerprint ===")
    fp = generate_device_fingerprint()
    print(f"Fingerprint: {fp['fingerprint']}")
    print(f"Short ID:    {fp['fingerprint'][:16].upper()}")
    print(f"\nComponents:")
    for k, v in fp["components"].items():
        print(f"  {k}: {v}")
    print(f"\nPlatform: {fp['platform']}")
