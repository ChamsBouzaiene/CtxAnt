# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for ctxant.app.
#
# Build:
#   cd installer && pyinstaller ctxant.spec --noconfirm
#
# Output: dist/ctxant.app (menu-bar app, LSUIElement=1 so no Dock icon).

import os
import re
from pathlib import Path

PROJECT_ROOT = Path(os.path.abspath(os.path.join(SPECPATH, ".."))).resolve()
BACKEND_DIR = PROJECT_ROOT / "backend"
EXTENSION_DIR = PROJECT_ROOT / "extension"
ASSETS_DIR = BACKEND_DIR / "assets"

# Read __version__ without importing backend/ (which pulls in dotenv and
# sqlite side-effects we don't want at spec-parse time). A 3-line module
# is easy to regex; we keep the single source of truth in one place.
_version_py = (BACKEND_DIR / "__version__.py").read_text()
_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', _version_py)
APP_VERSION = _match.group(1) if _match else "0.0.0"

block_cipher = None


# The Chrome extension ships inside the .app so first-run users have it on
# their disk and can Load Unpacked from the menu bar's config folder.
# Assets (menu-bar PNG, any future bundled resources) sit at the top level
# so ctxant_app._asset_path("menubar.png") finds them at _MEIPASS/assets/…
datas = [
    (str(EXTENSION_DIR), "extension"),
    (str(ASSETS_DIR), "assets"),
]


a = Analysis(
    [str(BACKEND_DIR / "ctxant_app.py")],
    pathex=[str(BACKEND_DIR)],
    binaries=[],
    datas=datas,
    # Pull in packages PyInstaller can't always detect through lazy imports.
    hiddenimports=[
        "__version__",
        "agents",
        "agent_handlers",
        "bots",
        "browser_bridge",
        "claude_agent",
        "config",
        "db",
        "hub_handlers",
        "machine_tools",
        "main",
        "onboarding",
        "pairing",
        "scheduler",
        "telegram_handler",
        "updater",
        "usage",
        # Third-party lazy imports
        "apscheduler.schedulers.asyncio",
        "apscheduler.triggers.cron",
        "apscheduler.triggers.date",
        "apscheduler.triggers.interval",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # We don't ship a big science stack — save a few MB.
        "tkinter",
        "matplotlib",
        "numpy",
    ],
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
    name="CtxAnt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
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
    upx=False,
    upx_exclude=[],
    name="CtxAnt",
)

app = BUNDLE(
    coll,
    name="CtxAnt.app",
    icon=None,  # drop installer/icon.icns here once the icon is designed
    bundle_identifier="com.ctxant.desktop",
    info_plist={
        "CFBundleName": "CtxAnt",
        "CFBundleDisplayName": "CtxAnt",
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "LSUIElement": True,           # menu-bar only, no Dock icon
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "© 2026 ctxant",
        # We use webbrowser / subprocess open, not direct Apple Events, so
        # most of the privacy-permissions strings are not needed. If a user
        # reports a permission prompt, add the matching NSUsageDescription.
    },
)
