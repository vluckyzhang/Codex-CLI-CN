# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

project_root = Path.cwd()

datas = [
    (str(project_root / "scripts"), "scripts"),
    (str(project_root / "translations"), "translations"),
    (str(project_root / "README.md"), "."),
    (str(project_root / "NOTICE.md"), "."),
    (str(project_root / "CHANGELOG.md"), "."),
]
datas += collect_data_files("customtkinter")

a = Analysis(
    [str(project_root / "gui" / "codex_cn_gui.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=["customtkinter", "darkdetect"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Codex-CLI-CN-GUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    uac_admin=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
