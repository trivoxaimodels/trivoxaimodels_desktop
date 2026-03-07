# Voxel Craft Desktop App - Nuitka Build Guide

## Security-First Build Process

This guide provides steps to build the Voxel Craft desktop app with maximum protection against reverse engineering.

### Protection Stack

```
PyQt6 (UI)
    ↓
PyArmor (obfuscation)
    ↓
Nuitka (compile to C)
    ↓
UPX (binary packing)
    ↓
Inno Setup / DMG / AppImage (installer)
```

---

## Step 1: Install Build Dependencies

### Windows
```cmd
pip install nuitka pyarmor upx
pip install pyqt6 pyside6
```

### Linux
```bash
pip install nuitka pyarmor upx
pip install pyqt6 pyside6
```

### macOS
```bash
pip install nuitka pyarmor upx
pip install pyqt6 pyside6
```

---

## Step 2: Install Nuitka Compiler

Nuitka requires a C compiler:

### Windows (Install MinGW-w64 or Clang)
```cmd
# Option 1: Install MinGW-w64
winget install mingw-w64

# Option 2: Install Clang (recommended)
winget install LLVM
```

### Linux
```bash
sudo apt install mingw-w64 clang gcc
```

### macOS
```bash
xcode-select --install
brew install llvm
```

---

## Step 3: Build Commands

### Quick Build (Windows)
```cmd
python build_nuitka.py --platform=windows
```

### Full Build with All Platforms
```cmd
python build_nuitka.py --all-platforms
```

### Build Options

| Flag | Description |
|------|-------------|
| `--platform=windows` | Build for Windows |
| `--platform=linux` | Build for Linux |
| `--platform=macos` | Build for macOS |
| `--all-platforms` | Build for all platforms |
| `--obfuscate` | Enable PyArmor obfuscation |
| `--onefile` | Single executable output |
| `--lto` | Enable LTO optimization |
| `--upx` | Compress with UPX |

---

## Step 4: Build Script Usage

### Basic Windows Build
```cmd
python build_nuitka.py
```

### Optimized Windows Build
```cmd
python build_nuitka.py --platform=windows --obfuscate --onefile --lto --upx
```

### All Platforms
```cmd
python build_nuitka.py --all-platforms --obfuscate --lto
```

---

## Step 5: Create Installers

### Windows (Inno Setup)
```cmd
python create_installer.py --platform=windows
```

### Linux (AppImage)
```cmd
python create_installer.py --platform=linux
```

### macOS (DMG)
```cmd
python create_installer.py --platform=macos
```

---

## Build Output

After building, executables will be in:
```
dist/
├── windows/
│   └── VoxelCraft.exe
├── linux/
│   └── VoxelCraft
└── macos/
    └── VoxelCraft.app
```

---

## Security Features Enabled

### 1. Code Obfuscation (PyArmor)
- Renames functions/classes
- Encrypts strings
- Removes debug info

### 2. Native Compilation (Nuitka)
- Python → C conversion
- Removes bytecode
- LTO optimization

### 3. Binary Compression (UPX)
- Compresses executable
- Hides binary structure
- Makes debugging harder

### 4. No Debug Symbols
- `--python-flag=no_docstrings`
- `--python-flag=no_site`
- Removes metadata

---

## Troubleshooting

### Issue: Nuitka fails with "C compiler not found"
**Solution:** Install MinGW-w64 or LLVM/Clang

### Issue: UPX compression fails
**Solution:** Use `--no-upx` flag or install UPX separately

### Issue: Build is too slow
**Solution:** Use `--jobs=auto` for parallel compilation

---

## Recommended Build Command

For maximum protection with reasonable build time:

```cmd
python build_nuitka.py --platform=windows --obfuscate --onefile --lto --upx
```

This produces a single, compressed, obfuscated executable that is very difficult to reverse engineer.
