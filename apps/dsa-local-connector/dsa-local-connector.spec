# -*- mode: python ; coding: utf-8 -*-
import sys

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'keyring',
        'keyring.backends.Windows',
        'keyring.backends.macOS',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DSA-Local-Connector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='DSA-Local-Connector.app',
        icon=None,
        bundle_identifier='com.dsa.local-connector',
        info_plist={
            'CFBundleDisplayName': 'DSA Local Connector',
            'NSHighResolutionCapable': True,
        },
    )
