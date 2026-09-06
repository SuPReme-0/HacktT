# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import glob
import site

# ==============================================================================
# 🔥 THE UNIVERSAL FFMPEG BYPASS (Conda + Pip)
# PyAV (used by Faster-Whisper) requires external FFmpeg DLLs.
# We dynamically locate them here whether you used Conda or standard Pip.
# ==============================================================================
ffmpeg_dlls = []

# 1. Check Conda Environment
conda_prefix = os.environ.get('CONDA_PREFIX', sys.prefix)
conda_bin_dir = os.path.join(conda_prefix, 'Library', 'bin')
if os.path.exists(conda_bin_dir):
    for dll in glob.glob(os.path.join(conda_bin_dir, 'av*.dll')) + \
               glob.glob(os.path.join(conda_bin_dir, 'sw*.dll')):
        ffmpeg_dlls.append((dll, '.'))

# 2. Check Standard Pip Environment (site-packages/av.libs)
for sp in site.getsitepackages():
    av_libs = os.path.join(sp, 'av.libs')
    if os.path.exists(av_libs):
        for dll in glob.glob(os.path.join(av_libs, '*.dll')):
            ffmpeg_dlls.append((dll, '.'))

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=ffmpeg_dlls, 
    datas=[], # Models are kept external to prevent a 10GB executable
    hiddenimports=[
        # Web Server Requirements
        'fastapi',
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
        'websockets.legacy.server',
        
        # OS & Hardware Hooks (CRITICAL for VRAM Guard)
        'wmi',
        'win32com',
        'pythoncom',
        
        # AI & Databases
        'llama_cpp',
        'lancedb',
        'kuzu',
        
        # Audio & Vision
        'faster_whisper',
        'ctranslate2', # Core engine for faster_whisper
        'av', 
        'sentence_transformers',
        'transformers',
        'torch',
        'sounddevice',
        'soundfile',
        
        # System Utilities
        'pynvml',
        'pyautogui',
        'mss',
        'watchdog',
        'PIL.Image'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude massive unused UI/Math frameworks to save compile time
    excludes=['tkinter', 'PyQt5', 'PySide2', 'matplotlib', 'scipy', 'pandas.tests'],  
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='hackt_sovereign_core',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False, # 🚨 CRITICAL: Must be False to prevent PyTorch/CUDA corruption
    console=True,  # Keep True so you can see the downloader logs in the terminal
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False, # 🚨 CRITICAL: Must be False
    upx_exclude=[],
    name='hackt_sovereign_core',
)