# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
# PyInstaller spec per costruire PrivacyBridge.app self-contained.
#
# Uso (dalla radice del progetto):
#     pyinstaller --clean --noconfirm --workpath build/pyinstaller \
#         --distpath dist build/PrivacyBridge.spec
#
# Il --workpath esplicito serve: il default di PyInstaller è ./build,
# che qui è già la cartella delle ricette e del bundle costruito a mano.
#
# Include il modello neurale (1.2 GB) nel bundle in Resources/modello:
# avvio.py cerca lì prima della cache HuggingFace, così l'app funziona
# anche senza rete e senza cache utente.
#
# Se torch / transformers cambiano major, potrebbe servire aggiornare
# gli hidden imports e i collect_data_files. Vedi BLOCCHI.md § 11 per
# i tentativi documentati.

# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    copy_metadata,
)
import os
import sys
from pathlib import Path

# Lo spec vive in build/, quindi la radice del progetto è un livello sopra.
BUILD = Path(os.path.abspath(SPEC)).parent
ROOT = BUILD.parent
SRC = ROOT / "src"
ASSETS = ROOT / "assets"

# ---------------------------------------------------------------------------
# Raccolta librerie pesanti (torch, transformers, presidio, tokenizers)
# ---------------------------------------------------------------------------

collect_targets = [
    "presidio_analyzer",
    "transformers",
    "tokenizers",
    "torch",
    "huggingface_hub",
    "safetensors",
    "spacy",
    # Modelli linguistici spaCy usati dall'analyzer Presidio.
    "it_core_news_lg",
    "en_core_web_lg",
]

extra_datas = []
extra_binaries = []
extra_hidden = []

for name in collect_targets:
    ds, bs, hs = collect_all(name)
    extra_datas += ds
    extra_binaries += bs
    extra_hidden += hs

# Metadata (dist-info) richiesti da importlib.metadata per alcuni pkg.
for name in ("torch", "tokenizers", "transformers", "huggingface_hub"):
    try:
        extra_datas += copy_metadata(name)
    except Exception:
        pass

# Dati del progetto: SOLO le liste che il motore legge a runtime.
# Non l'intera cartella: ci finivano dentro le liste grezze (che servono
# solo a rigenerare i TSV) e, in una versione precedente, perfino un
# vault con dentro dati veri.
extra_datas += [(str(SRC / "data" / "liste"), "data/liste")]
# Frontend: index.html.
extra_datas += [(str(SRC / "api" / "static"), "api/static")]

# Il modello neurale (1.2 GB) NON è aggiunto ai datas di PyInstaller
# — comprime male e allunga il build di parecchi minuti. Viene
# copiato manualmente in Resources/modello dopo il build (vedi
# build/build_bundle.sh).

# ---------------------------------------------------------------------------
# Analisi
# ---------------------------------------------------------------------------

a = Analysis(
    [str(SRC / "avvio.py")],
    pathex=[str(SRC)],
    binaries=extra_binaries,
    datas=extra_datas,
    hiddenimports=[
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "webview",
        "webview.platforms.cocoa",
        "email.mime",
        "sqlite3",
        # OCR nativo (PARTE 2): pyobjc Vision su macOS, pypdfium2 per
        # la rasterizzazione. Su Windows Vision/Quartz non esistono e
        # PyInstaller li salta (moduli condizionali).
        "pypdfium2",
    ] + extra_hidden + (
        ["Vision", "Quartz", "Foundation"] if sys.platform == "darwin" else
        ["winsdk.windows.media.ocr", "winsdk.windows.graphics.imaging",
         "winsdk.windows.storage.streams"] if sys.platform == "win32" else []
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Pesano tanto e non servono nell'app compilata.
        "tkinter",
        "matplotlib",
        "notebook",
        "IPython",
        "pytest",
        "playwright",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PrivacyBridge",
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
    icon=str(ASSETS / "icon.icns"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PrivacyBridge",
)

app = BUNDLE(
    coll,
    name="PrivacyBridge.app",
    icon=str(ASSETS / "icon.icns"),
    bundle_identifier="com.andreasforna.privacybridge",
    version="1.0.0",
    info_plist={
        "CFBundleName": "PrivacyBridge",
        "CFBundleDisplayName": "PrivacyBridge",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHumanReadableCopyright": "© 2026 Andrea Sforna — Licenza MIT",
    },
)
