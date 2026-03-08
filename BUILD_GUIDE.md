# VoxelCraft Desktop Application - Build Guide

Complete guide for building the VoxelCraft desktop application with professional Windows installer.

## Prerequisites

### Required Software

| Software | Version | Download |
|----------|---------|----------|
| Python | 3.9+ | https://www.python.org/downloads/ |
| Inno Setup 6 | 6.x | https://jrsoftware.org/isdl.php |

### System Requirements

- Windows 10/11 (64-bit)
- 8GB RAM minimum (16GB recommended)
- 10GB free disk space

## Quick Start

### Simple Build (Executable Only)

```batch
build.bat
```

This creates a standalone executable at `dist\VoxelCraft.exe`.

### Complete Build (Executable + Installer)

```batch
build_complete.bat
```

This creates:
- `dist\VoxelCraft.exe` - Standalone executable
- `installer\output\VoxelCraft_Setup_v1.0.0.exe` - Windows installer
- `VoxelCraft_v1.0.0_Complete.zip` - Distribution package

## Build Process Details

### Step 1: Virtual Environment Setup

The build scripts automatically create and use a virtual environment:

```
venv/
├── Scripts/
│   ├── activate.bat
│   ├── python.exe
│   └── pip.exe
└── Lib/
    └── site-packages/
```

### Step 2: Dependency Installation

All dependencies from `requirements.txt` are installed:

```
pip install -r requirements.txt
```

Key dependencies:
- **PySide6** - Qt framework for desktop UI
- **tripo3d** - Tripo3D API SDK
- **supabase** - Authentication backend
- **trimesh** - 3D model processing
- **open3d** - Point cloud processing
- **aiohttp** - Async HTTP client

### Step 3: Executable Build

PyInstaller bundles the application:

```
pyinstaller VoxelCraft.spec --clean --noconfirm
```

Build time: 30-60 minutes (depending on system)

### Step 4: Installer Creation (Optional)

Inno Setup creates a professional installer:

```
installer\VoxelCraft.iss
```

Features:
- Custom branding with logo
- License agreement page
- Installation path selection
- Desktop shortcut option
- Launch after install option
- Clean uninstall support

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Supabase Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_key

# API Keys (Optional - users can enter in app)
TRIPO3D_API_KEY=
HITEM3D_CLIENT_ID=
HITEM3D_CLIENT_SECRET=
```

### Version Information

Update version in these files:
- `main.py` - `app.setApplicationVersion("1.0.0")`
- `installer/VoxelCraft.iss` - `#define AppVersion "1.0.0"`
- `build_complete.bat` - `set "APP_VERSION=1.0.0"`

## Custom Branding

### Installer Logo

Create these files in `installer/setup_assets/`:

| File | Size | Purpose |
|------|------|---------|
| `logo.bmp` | 164x314 px | Setup wizard sidebar |
| `logo.ico` | 256x256 px | Setup and app icon |

### Application Icon

Place `logo.ico` in `assets/logo/` for the application icon.

## Troubleshooting

### Common Issues

#### 1. "Python is not installed or not in PATH"
- Install Python 3.9+
- Check "Add Python to PATH" during installation

#### 2. "Inno Setup 6 not found"
- Install Inno Setup 6 from https://jrsoftware.org/isdl.php
- Or use `build.bat` for executable-only build

#### 3. "Failed to install dependencies"
- Check internet connection
- Try: `pip install --upgrade pip`
- Try: `pip cache purge`

#### 4. "Build failed! Please check the error messages"
- Check `build/VoxelCraft/warn-VoxelCraft.txt` for warnings
- Set `console=True` in `VoxelCraft.spec` for debug output
- Check for missing imports in `hiddenimports` list

#### 5. "Executable not found after build"
- Check if PyInstaller completed successfully
- Look for errors in build output
- Verify `VoxelCraft.spec` is correct

### Debug Mode

To see console output for debugging:

1. Edit `VoxelCraft.spec`
2. Change `console=False` to `console=True`
3. Rebuild with `build.bat`

### Missing Dependencies

If you get import errors when running the executable:

1. Add the missing module to `hiddenimports` in `VoxelCraft.spec`
2. Rebuild the application

Example:
```python
hiddenimports = [
    # ... existing imports ...
    'missing_module_name',
]
```

## File Structure

```
VoxelCraft_desktop_app/
├── build.bat              # Simple build script
├── build_complete.bat     # Full build with installer
├── requirements.txt       # Python dependencies
├── VoxelCraft.spec          # PyInstaller configuration
├── main.py                # Application entry point
├── .env.example           # Environment template
├── installer/
│   ├── VoxelCraft.iss       # Inno Setup script
│   ├── setup_assets/
│   │   ├── LICENSE.txt
│   │   ├── logo.bmp       # Optional
│   │   └── logo.ico       # Optional
│   └── output/            # Generated installer
├── assets/
│   └── logo/
│       └── logo.svg
├── config/
│   ├── __init__.py
│   ├── payment_config.py
│   └── settings.py
├── core/
│   ├── __init__.py
│   ├── credit_manager.py
│   ├── device_fingerprint.py
│   ├── hitem3d_api.py
│   ├── logger.py
│   ├── meshy_ai_client.py
│   ├── multiangle_processor.py
│   ├── neural4d_client.py
│   ├── session_manager.py
│   ├── supabase_client.py
│   ├── tripo3d_client.py
│   ├── unified_api.py
│   └── unified_pipeline.py
└── ui/
    ├── __init__.py
    ├── auth_dialog.py
    ├── main_window.py
    └── styles/
        └── styles.qss
```

## Distribution

### Testing the Installer

1. Run `installer\output\VoxelCraft_Setup_v1.0.0.exe`
2. Verify installation in `C:\Program Files\VoxelCraft`
3. Test desktop shortcut
4. Test application launch
5. Test uninstall from Control Panel

### Distribution Package

The `VoxelCraft_v1.0.0_Complete.zip` contains:
- Windows installer executable
- Ready for distribution

### Auto-Update Support

To enable auto-updates:
1. Host `updates.json` on your server
2. Configure update URL in application settings

## Support

For issues or questions:
- Check the troubleshooting section above
- Review build logs in `build_log.txt`
- Contact support at support@VoxelCraft.com
