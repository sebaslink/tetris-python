# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['tetris.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('img', 'img'),
        ('media', 'media'),
        ('music', 'music'),
        ('tetrisonline-zodiacogame-firebase-adminsdk-fbsvc-f79d564b0f.json', '.')
    ],
    hiddenimports=[
        'firebase_admin',
        'firebase_admin.credentials',
        'firebase_admin.firestore',
        'google.cloud.firestore',
        'cv2',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'pygame',
        'pygame.mixer'
    ],
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
    [],
    exclude_binaries=True,
    name='ZodiacoGame',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='img/icons8-tetris-64.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ZodiacoGame',
)
