# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for Trivox Models Desktop Application

Build command:
    pyinstaller VoxelCraft.spec

Output:
    dist/VoxelCraft.exe (single file executable)
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata

block_cipher = None

# Get the project root
project_root = Path(SPECPATH)

# Collect all data files
datas = [
    (str(project_root / 'ui' / 'styles'), 'ui/styles'),
    (str(project_root / 'assets'), 'assets'),
    (str(project_root / 'config'), 'config'),
    (str(project_root / 'viewer.html'), '.'),
]

# Include .env file if it exists
if (project_root / '.env').exists():
    datas.append((str(project_root / '.env'), '.'))

# Collect pyparsing metadata and data
datas += copy_metadata('pyparsing')
datas += collect_data_files('pyparsing')

# Collect pyparsing modules and data completely
hiddenimports = collect_submodules('pyparsing')

# Note: pkg_resources is excluded to avoid pyparsing issues
# If needed, use packaging module directly instead

# Hidden imports (modules that PyInstaller might miss)
hiddenimports += [
    # Qt Framework
    'PySide6.QtCore',
    'PySide6.QtWidgets',
    'PySide6.QtGui',
    'PySide6.QtNetwork',
    'PySide6.QtXml',
    
    # Supabase and auth
    'supabase',
    'supabase.client',
    'supabase.lib',
    'supabase.lib.client',
    'postgrest',
    'storage3',
    'gotrue',
    'realtime',
    'httpx',
    'httpcore',
    'h11',
    'h2',
    'hpack',
    'hyperframe',
    'hstspreload',
    
    # Async support
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
    'sniffio',
    'asyncio',
    
    # HTTP clients
    'aiohttp',
    'aiohttp.client',
    'aiohttp.connector',
    'aiofiles',
    'requests',
    
    # Image processing
    'PIL',
    'PIL.Image',
    'PIL._imaging',
    'pillow',
    'numpy',
    'cv2',
    'opencv_python_headless',
    
    # 3D processing
    'trimesh',
    'trimesh.exchange',
    'trimesh.creation',
    'trimesh.io',
    'open3d',
    'open3d.cpu',
    'open3d.cpu.pybind',
    
    # AI/ML for local processing
    'torch',
    'torch.nn',
    'torch.nn.functional',
    'torch.utils',
    'torch.utils.data',
    'torch.utils.data.dataloader',
    'torch.utils.data.dataset',
    'torchvision',
    'torchvision.transforms',
    'diffusers',
    'diffusers.pipelines',
    'diffusers.schedulers',
    'accelerate',
    'transformers',
    'transformers.models',
    'transformers.tokenization_utils',
    
    # Tripo3D SDK
    'tripo3d',
    
    # Auth
    'bcrypt',
    
    # Utilities
    'dotenv',
    'python_dotenv',
    'dateutil',
    'psutil',
    'platformdirs',
    
    # Local processing modules
    'core.server_auth',
    'core.auth',
    'core.license_manager',
    'core.payment_factory',
    'core.admin_manager',
    'core.secret_manager',
    'core.pipeline',
    'core.inference.model_manager',
    'core.inference.triposr',
    'core.postprocess.cleanup',
    'core.postprocess.advanced_mesh_processor',
    'core.providers.gumroad',
    'core.providers.base',
    
    # Data handling
    'json',
    'hashlib',
    'uuid',
    'dataclasses',
    'typing_extensions',
    
    # Encoding/Compression
    'base64',
    'mimetypes',
    'zipfile',
    'gzip',
    'zlib',
    
    # XML (needed by pkg_resources/plistlib)
    'xml',
    'xml.etree',
    'xml.etree.ElementTree',
    'xml.parsers',
    'xml.parsers.expat',
    'plistlib',
    
    # Email (needed by pkg_resources)
    'email',
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
    'email.mime.base',
    'email.utils',
    'email.header',
    'email.encoders',
    
    # Pyparsing (needed by pkg_resources/packaging)
    'pyparsing',
    'pyparsing.util',
    'pyparsing.unicode',
    'pyparsing.exceptions',
    'pyparsing.actions',
    'pyparsing.core',
    'pyparsing.results',
    'pyparsing.helpers',
    'pyparsing.grammar',
    'pyparsing.testing',
    'pyparsing.common',
    
    # Packaging (needed by pkg_resources)
    'packaging',
    'packaging.requirements',
    'packaging.specifiers',
    'packaging.markers',
    'packaging.version',
    'packaging.utils',
    'packaging.tags',
    
    # System
    'platform',
    'subprocess',
    'ctypes',
    'unittest',
    'typing',
    
    # Logging
    'logging',
    'logging.handlers',
]

# Exclude unnecessary modules and files to reduce size and improve security
excludes = [
    'tkinter',
    'matplotlib',
    'scipy',
    'pandas',
    'IPython',
    'jupyter',
    'notebook',
    'pytest',
    'sphinx',
    'docutils',
    'test',
    'tests',
    'pkg_resources',
    # Exclude venv and env folders
    'venv',
    'env',
    '.env',
    '.env.example',
    '.env.local',
]

a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(project_root / 'hooks')],
    hooksconfig={},
    runtime_hooks=[str(project_root / 'hooks' / 'rth_pyparsing.py')],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VoxelCraft',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'installer' / 'setup_assets' / 'logo.ico') if (project_root / 'installer' / 'setup_assets' / 'logo.ico').exists() else None,
)
