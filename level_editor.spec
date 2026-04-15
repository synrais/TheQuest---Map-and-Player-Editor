# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['level_editor.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('sprites', 'sprites'),
    ],
    hiddenimports=[
        'PIL._imaging',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # safe trims
        'unittest',
        'pydoc',
        'doctest',

        # remove pywin32 bloat
        'win32com',
        'pythoncom',
        'pywintypes',

        # unused Pillow parts
        'PIL.ImageQt',
        'PIL.ImageCms',
        'PIL.BmpImagePlugin',
        'PIL.GifImagePlugin',
        'PIL.TiffImagePlugin',

        # optional heavy libs
        'numpy',
        'matplotlib',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='The Quest Map and Player Editor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)