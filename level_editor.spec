# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for The Quest Level Editor
#
# Build command (run from the folder containing this file):
#   pyinstaller level_editor.spec
#
# Output: dist/Level Editor.exe
#
# Requirements:
#   pip install pyinstaller pillow

block_cipher = None

a = Analysis(
    ['level_editor.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('sprites', 'sprites'),   # bundle the sprites folder
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='Level Editor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',    # uncomment and point to a .ico file if you have one
)
