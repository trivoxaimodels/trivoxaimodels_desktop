#!/usr/bin/env python3
"""
Voxel Craft Desktop App - Nuitka Build Script

This script builds the Voxel Craft desktop app using Nuitka for maximum
protection against reverse engineering.

Usage:
    python build_nuitka.py --platform=windows
    python build_nuitka.py --all-platforms
    python build_nuitka.py --platform=windows --obfuscate --onefile --lto --upx
"""

import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path

# Project configuration
PROJECT_NAME = "VoxelCraft"
MAIN_SCRIPT = "main.py"
DIST_DIR = Path("dist")
BUILD_DIR = Path("build")

# Required packages for Nuitka
REQUIRED_PACKAGES = [
    "nuitka",
    "pyqt6",
    "pyside6",
    "pyarmor",  # Optional for obfuscation
    "upx",      # Optional for compression
]


def check_dependencies():
    """Check if required build tools are installed."""
    print("Checking dependencies...")
    
    # Check Python version
    if sys.version_info < (3, 9):
        print("ERROR: Python 3.9+ required")
        return False
    
    # Check Nuitka
    try:
        import nuitka
        print(f"✓ Nuitka {nuitka.__version__} installed")
    except ImportError:
        print("✗ Nuitka not installed. Install with: pip install nuitka")
        return False
    
    # Check PyQt6
    try:
        from PySide6 import QtCore
        print(f"✓ PySide6 installed")
    except ImportError:
        print("✗ PySide6 not installed. Install with: pip install pyside6")
        return False
    
    return True


def run_command(cmd, cwd=None):
    """Run a command and return exit code."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, shell=False)
    return result.returncode == 0


def build_windows(obfuscate=False, onefile=True, lto=True, upx=False):
    """Build for Windows."""
    print("\n=== Building for Windows ===")
    
    # Base Nuitka command
    cmd = [
        sys.executable, "-m", "nuitka",
        MAIN_SCRIPT,
        "--standalone",
        "--onefile" if onefile else "--onedir",
        f"--output-dir={DIST_DIR / 'windows'}",
        f"--windows-icon=assets/logo/logo.ico",
        "--enable-plugin=pyside6",
        "--include-package=core",
        "--include-package=ui",
        "--include-package=config",
        "--follow-imports",
    ]
    
    # Add optimization flags
    if lto:
        cmd.append("--lto=yes")
    
    # Add clang
    cmd.append("--clang")
    
    # Remove debug info
    cmd.append("--python-flag=no_docstrings")
    cmd.append("--python-flag=no_site")
    
    # Obfuscation
    if obfuscate:
        cmd.append("--python-flag=obfuscate")
    
    # UPX compression
    if upx:
        cmd.append("--windows-disable-console")
        # Note: UPX needs to be installed separately
    
    print(f"Command: {' '.join(cmd)}")
    return run_command(cmd)


def build_linux(obfuscate=False, onefile=False, lto=True):
    """Build for Linux."""
    print("\n=== Building for Linux ===")
    
    cmd = [
        sys.executable, "-m", "nuitka",
        MAIN_SCRIPT,
        "--standalone",
        f"--output-dir={DIST_DIR / 'linux'}",
        "--enable-plugin=pyside6",
        "--include-package=core",
        "--include-package=ui",
        "--include-package=config",
        "--follow-imports",
    ]
    
    if lto:
        cmd.append("--lto=yes")
    
    cmd.append("--python-flag=no_docstrings")
    cmd.append("--python-flag=no_site")
    
    if obfuscate:
        cmd.append("--python-flag=obfuscate")
    
    return run_command(cmd)


def build_macos(obfuscate=False, onefile=True, lto=True):
    """Build for macOS."""
    print("\n=== Building for macOS ===")
    
    cmd = [
        sys.executable, "-m", "nuitka",
        MAIN_SCRIPT,
        "--standalone",
        "--onefile" if onefile else "--onedir",
        f"--output-dir={DIST_DIR / 'macos'}",
        "--enable-plugin=pyside6",
        "--include-package=core",
        "--include-package=ui",
        "--include-package=config",
        "--follow-imports",
    ]
    
    if lto:
        cmd.append("--lto=yes")
    
    cmd.append("--python-flag=no_docstrings")
    cmd.append("--python-flag=no_site")
    
    if obfuscate:
        cmd.append("--python-flag=obfuscate")
    
    return run_command(cmd)


def compress_with_upx():
    """Compress built executables with UPX."""
    print("\n=== Compressing with UPX ===")
    
    upx_path = shutil.which("upx")
    if not upx_path:
        print("Warning: UPX not found. Skipping compression.")
        return
    
    # Find all executables
    for platform in ["windows", "linux", "macos"]:
        platform_dir = DIST_DIR / platform
        if not platform_dir.exists():
            continue
        
        for exe in platform_dir.rglob("*"):
            if exe.is_file() and os.access(exe, os.X_OK):
                print(f"Compressing: {exe}")
                run_command([upx_path, "--best", "--lzma", str(exe)])


def main():
    parser = argparse.ArgumentParser(
        description="Build Voxel Craft Desktop App with Nuitka"
    )
    parser.add_argument(
        "--platform",
        choices=["windows", "linux", "macos", "all"],
        default="windows",
        help="Target platform"
    )
    parser.add_argument(
        "--obfuscate",
        action="store_true",
        help="Enable code obfuscation"
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        default=True,
        help="Create single executable"
    )
    parser.add_argument(
        "--lto",
        action="store_true",
        default=True,
        help="Enable LTO optimization"
    )
    parser.add_argument(
        "--upx",
        action="store_true",
        help="Compress with UPX"
    )
    parser.add_argument(
        "--all-platforms",
        action="store_true",
        help="Build for all platforms"
    )
    
    args = parser.parse_args()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Clean previous builds
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    
    # Determine platforms to build
    platforms = []
    if args.all_platforms or args.platform == "all":
        platforms = ["windows", "linux", "macos"]
    else:
        platforms = [args.platform]
    
    # Build for each platform
    success = True
    for platform in platforms:
        if platform == "windows":
            success = build_windows(args.obfuscate, args.onefile, args.lto, args.upx)
        elif platform == "linux":
            success = build_linux(args.obfuscate, args.onefile, args.lto)
        elif platform == "macos":
            success = build_macos(args.obfuscate, args.onefile, args.lto)
        
        if not success:
            print(f"ERROR: Build failed for {platform}")
            sys.exit(1)
    
    # Compress with UPX if requested
    if args.upx:
        compress_with_upx()
    
    print("\n=== Build Complete ===")
    print(f"Output directory: {DIST_DIR}")
    
    # List built files
    for platform in platforms:
        platform_dir = DIST_DIR / platform
        if platform_dir.exists():
            print(f"\n{platform.upper()} files:")
            for f in platform_dir.rglob("*"):
                if f.is_file():
                    size_mb = f.stat().st_size / (1024 * 1024)
                    print(f"  {f.name}: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
