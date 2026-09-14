#!/usr/bin/env bash
# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
# Costruisce PrivacyBridge.app self-contained via PyInstaller + copia
# il modello neurale + crea il .dmg per distribuzione.
#
# Uso (da qualunque cartella):
#     bash build/build_bundle.sh
#
# Output:
#     dist/PrivacyBridge.app  — bundle self-contained
#     dist/PrivacyBridge.dmg  — immagine di installazione

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d venv ]; then
    echo "ERRORE: venv non trovato. Esegui prima 'python3 -m venv venv && ..." >&2
    exit 1
fi
# shellcheck disable=SC1091
source venv/bin/activate

# Il modello non sta in git (1,2 GB): la copia di riferimento è quella
# dentro il bundle costruito a mano, che è anche l'unica che esiste su
# questa macchina.
MODELLO_SORGENTE="$ROOT/build/PrivacyBridge.app/Contents/Resources/modello"
if [ ! -d "$MODELLO_SORGENTE" ]; then
    echo "ERRORE: modello non trovato in $MODELLO_SORGENTE" >&2
    echo "  Scaricalo prima con: python -m huggingface_hub download" >&2
    echo "  rizzoaiacademy/rizzo-pii-0.3B --revision <hash> --local-dir \\" >&2
    echo "  \"$MODELLO_SORGENTE\"" >&2
    exit 1
fi

# workpath esplicito: il default di PyInstaller è ./build, che qui è già
# la cartella delle ricette e del bundle a mano. Lasciarglielo scrivere
# dentro mescolerebbe sorgenti e file temporanei nello stesso posto.
echo "==> PyInstaller build"
pyinstaller --clean --noconfirm \
    --workpath "$ROOT/build/pyinstaller" \
    --distpath "$ROOT/dist" \
    "$ROOT/build/PrivacyBridge.spec"

echo "==> Copia modello nel bundle"
BUNDLE="dist/PrivacyBridge.app"
mkdir -p "$BUNDLE/Contents/Resources"
if [ -d "$BUNDLE/Contents/Resources/modello" ]; then
    rm -rf "$BUNDLE/Contents/Resources/modello"
fi
cp -R "$MODELLO_SORGENTE" "$BUNDLE/Contents/Resources/modello"

echo "==> Bundle dimensione:"
du -sh "$BUNDLE"

echo "==> Costruisco .dmg"
DMG="dist/PrivacyBridge.dmg"
rm -f "$DMG"
# Finestra di installazione classica: l'app a sinistra, il collegamento
# ad Applicazioni a destra, si trascina l'una sull'altro.
STAGING="$(mktemp -d)"
cp -R "$BUNDLE" "$STAGING/"
ln -s /Applications "$STAGING/Applications"
hdiutil create -volname "PrivacyBridge" -srcfolder "$STAGING" \
    -ov -format UDZO "$DMG"
rm -rf "$STAGING"

echo "==> Fatto."
echo "    $BUNDLE ($(du -sh "$BUNDLE" | cut -f1))"
echo "    $DMG ($(du -sh "$DMG" | cut -f1))"
