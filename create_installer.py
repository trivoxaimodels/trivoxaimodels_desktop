#!/usr/bin/env python3
"""
Voxel Craft Desktop App - Installer Creator

Creates installers for Windows, Linux, and macOS platforms.

Usage:
    python create_installer.py --platform=windows
    python create_installer.py --all-platforms
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path

# Project configuration
PROJECT_NAME = "VoxelCraft"
VERSION = "2.1.0"
DIST_DIR = Path("dist")
INSTALLER_DIR = Path("installers")

# Installer configurations
WINDOWS_INSTALLER_CONFIG = {
    "name": "VoxelCraft",
    "version": VERSION,
    "publisher": "Trivox AI Models",
    "exe_name": "VoxelCraft.exe",
    "output": "VoxelCraft-Setup.exe"
}

LINUX_INSTALLER_CONFIG = {
    "name": "voxelcraft",
    "version": VERSION,
    "publisher": "Trivox AI Models",
    "exe_name": "VoxelCraft",
    "output": "VoxelCraft.AppImage"
}

MACOS_INSTALLER_CONFIG = {
    "name": "VoxelCraft",
    "version": VERSION,
    "publisher": "Trivox AI Models",
    "exe_name": "VoxelCraft",
    "output": "VoxelCraft.dmg"
}


def run_command(cmd, cwd=None):
    """Run a command and return success status."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, shell=False)
    return result.returncode == 0


def create_windows_installer():
    """Create Windows installer using Inno Setup."""
    print("\n=== Creating Windows Installer ===")
    
    inno_setup_path = shutil.which("iscc")
    if not inno_setup_path:
        # Try common paths
        possible_paths = [
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                inno_setup_path = path
                break
    
    if not inno_setup_path:
        print("Inno Setup not found. Please install from https://jrsoftware.org/isdl.php")
        print("Alternatively, use the portable .exe from dist/windows/")
        return False
    
    # Create Inno Setup script
    iss_content = f"""
[Setup]
AppName={WINDOWS_INSTALLER_CONFIG['name']}
AppVersion={WINDOWS_INSTALLER_CONFIG['version']}
AppPublisher={WINDOWS_INSTALLER_CONFIG['publisher']}
DefaultDirName={{autopf}}\\{WINDOWS_INSTALLER_CONFIG['name']}
DefaultGroupName={WINDOWS_INSTALLER_CONFIG['name']}
OutputDir=..\\{INSTALLER_DIR}
OutputBaseName={WINDOWS_INSTALLER_CONFIG['output']}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Files]
Source=..\\dist\\windows\\*; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{{group}}\\{WINDOWS_INSTALLER_CONFIG['name']}"; Filename: "{{app}}\\{WINDOWS_INSTALLER_CONFIG['exe_name']}"
Name: "{{autodesktop}}\\{WINDOWS_INSTALLER_CONFIG['name']}"; Filename: "{{app}}\\{WINDOWS_INSTALLER_CONFIG['exe_name']}"
"""
    
    iss_file = Path("installer/VoxelCraft.iss")
    iss_file.parent.mkdir(exist_ok=True)
    iss_file.write_text(iss_content)
    
    # Build installer
    cmd = [inno_setup_path, str(iss_file)]
    return run_command(cmd, cwd="installer")


def create_linux_appimage():
    """Create Linux AppImage."""
    print("\n=== Creating Linux AppImage ===")
    
    # Check for appimagetool
    appimagetool_path = shutil.which("appimagetool")
    if not appimagetool_path:
        print("appimagetool not found. Please install from https://github.com/AppImage/AppImageKit")
        return False
    
    # Create AppDir structure
    appdir = Path("AppDir")
    if appdir.exists():
        shutil.rmtree(appdir)
    appdir.mkdir()
    
    # Copy files
    linux_dist = DIST_DIR / "linux"
    if linux_dist.exists():
        for item in linux_dist.iterdir():
            shutil.copytree(item, appdir / item.name, dirs_exist_ok=True)
    
    # Create AppRun
    apprun = appdir / "AppRun"
    apprun.write_text(f"""#!/bin/bash
exec "$(dirname "$0")/{LINUX_INSTALLER_CONFIG['exe_name']}" "$@"
""")
    os.chmod(apprun, 0o755)
    
    # Create desktop file
    desktop = appdir / "voxelcraft.desktop"
    desktop.write_text(f"""[Desktop Entry]
Name={LINUX_INSTALLER_CONFIG['name']}
Comment=AI-powered 3D Model Generator
Exec={LINUX_INSTALLER_CONFIG['exe_name']}
Icon=voxelcraft
Type=Application
Categories=Graphics;3DGraphics;
""")
    
    # Create icon
    icon_src = Path("assets/logo/logo.png")
    if icon_src.exists():
        shutil.copy(icon_src, appdir / "voxelcraft.png")
    
    # Build AppImage
    cmd = [appimagetool_path, str(appdir), str(INSTALLER_DIR / LINUX_INSTALLER_CONFIG['output'])]
    return run_command(cmd)


def create_macos_dmg():
    """Create macOS DMG."""
    print("\n=== Creating macOS DMG ===")
    
    # Check for create-dmg
    create_dmg_path = shutil.which("create-dmg")
    if not create_dmg_path:
        print("create-dmg not found. Install: brew install create-dmg")
        return False
    
    # Create DMG
    dmg_path = INSTALLER_DIR / MACOS_INSTALLER_CONFIG['output']
    cmd = [
        create_dmg_path,
        "--volname", MACOS_INSTALLER_CONFIG['name'],
        "--window-pos", "200", "120",
        "--size", "400",
        "--icon-size", "100",
        "--icon", MACOS_INSTALLER_CONFIG['name'], "150", "200",
        str(dmg_path),
        str(DIST_DIR / "macos" / f"{MACOS_INSTALLER_CONFIG['name']}.app")
    ]
    
    return run_command(cmd)


def create_portable_zip():
    """Create portable ZIP archives."""
    print("\n=== Creating Portable ZIPs ===")
    
    for platform in ["windows", "linux", "macos"]:
        platform_dir = DIST_DIR / platform
        if not platform_dir.exists():
            continue
        
        zip_name = f"{PROJECT_NAME}-{VERSION}-{platform}.zip"
        zip_path = INSTALLER_DIR / zip_name
        
        print(f"Creating {zip_name}...")
        
        # Create zip
        import zipfile
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(platform_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(platform_dir)
                    zipf.write(file_path, arcname)
        
        print(f"Created: {zip_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Create installers for Voxel Craft Desktop App"
    )
    parser.add_argument(
        "--platform",
        choices=["windows", "linux", "macos", "all"],
        default="all",
        help="Target platform"
    )
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Create portable ZIP archives"
    )
    
    args = parser.parse_args()
    
    # Create installer directory
    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    
    # Determine platforms
    platforms = []
    if args.platform == "all":
        platforms = ["windows", "linux", "macos"]
    else:
        platforms = [args.platform]
    
    # Create installers
    for platform in platforms:
        if platform == "windows":
            create_windows_installer()
        elif platform == "linux":
            create_linux_appimage()
        elif platform == "macos":
            create_macos_dmg()
    
    # Create portable ZIPs
    if args.portable:
        create_portable_zip()
    
    print("\n=== Installer Creation Complete ===")
    print(f"Output directory: {INSTALLER_DIR}")
    
    # List created files
    for f in INSTALLER_DIR.iterdir():
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name}: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
