#!/bin/bash
# verifica_tutto.sh — Esegue le suite di test di PrivacyBridge e stampa
# un riepilogo leggibile con tempi. Zero-arg: attiva venv, lancia pytest,
# esce con lo stesso codice di pytest.
set -u

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

sep() { printf '%s\n' "----------------------------------------------------------------"; }

t0=$(python -c "import time;print(time.time())")

sep
echo "PrivacyBridge — verifica_tutto"
echo "Data: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Python: $(python --version 2>&1)"
sep

echo
echo ">> Suite motore + documenti (incl. OCR)"
sep
t_backend0=$(python -c "import time;print(time.time())")
python -m pytest tests/test_motore.py tests/test_documenti.py -v --tb=short
rc_backend=$?
t_backend=$(python -c "import time;print(f'{time.time()-$t_backend0:.1f}')")

echo
echo ">> Suite tassonomia PII (recognizer deterministici)"
sep
t_tax0=$(python -c "import time;print(time.time())")
python -m pytest tests/test_tassonomia.py -v --tb=short
rc_tax=$?
t_tax=$(python -c "import time;print(f'{time.time()-$t_tax0:.1f}')")

echo
echo ">> Suite avversariale (500+ casi sistematici)"
sep
t_avv0=$(python -c "import time;print(time.time())")
python -m pytest tests/test_avversariale.py -q --tb=short
rc_avv=$?
t_avv=$(python -c "import time;print(f'{time.time()-$t_avv0:.1f}')")

echo
echo ">> Matrice input (struttura/grafia/lingua/dimensione/qualità)"
sep
t_mat0=$(python -c "import time;print(time.time())")
python -m benchmark.matrice_input
rc_mat=$?
t_mat=$(python -c "import time;print(f'{time.time()-$t_mat0:.1f}')")

echo
echo ">> Documenti reali dell'utente (numeri di consegna)"
sep
t_doc0=$(python -c "import time;print(time.time())")
python -m benchmark.utente > benchmark/documenti_utente_output.txt 2>&1
rc_doc=$?
tail -8 benchmark/documenti_utente_output.txt
t_doc=$(python -c "import time;print(f'{time.time()-$t_doc0:.1f}')")

echo
echo ">> Suite garanzie (6 garanzie di prodotto)"
sep
t_g0=$(python -c "import time;print(time.time())")
python -m pytest tests/test_garanzie.py -v --tb=short
rc_g=$?
t_g=$(python -c "import time;print(f'{time.time()-$t_g0:.1f}')")

echo
echo ">> Suite interfaccia (Playwright, Chromium headless)"
sep
t_ui0=$(python -c "import time;print(time.time())")
python -m pytest tests/test_interfaccia.py -v --tb=short
rc_ui=$?
t_ui=$(python -c "import time;print(f'{time.time()-$t_ui0:.1f}')")

echo
echo ">> Bundle macOS (esistenza + avvio + /health)"
sep
t_bundle0=$(python -c "import time;print(time.time())")
# Si prova prima dist/: è il bundle che esce da PyInstaller ed è quello
# che finisce nel .dmg consegnato. build/ tiene la versione montata a mano
# da cui si preleva il modello, e serve solo come ripiego.
BUNDLE="dist/PrivacyBridge.app/Contents/MacOS/PrivacyBridge"
[ -x "$BUNDLE" ] || BUNDLE="build/PrivacyBridge.app/Contents/MacOS/PrivacyBridge"
rc_bundle=0
if [ ! -x "$BUNDLE" ]; then
    echo "  [skip] bundle non presente: costruiscilo con build/build_bundle.sh"
    rc_bundle=0
else
    echo "  bundle in prova: $BUNDLE"
    TMP=$(mktemp -d)
    PRIVACYBRIDGE_DATA_DIR="$TMP" "$BUNDLE" >/dev/null 2>&1 &
    PID=$!
    sleep 25
    PORT=$(grep -o "porta [0-9]*" "$TMP/log.txt" 2>/dev/null | head -1 | awk '{print $2}')
    if [ -z "$PORT" ]; then
        echo "  [FAIL] bundle non ha aperto la porta (log: $TMP/log.txt)"
        cat "$TMP/log.txt" 2>/dev/null | tail -5
        rc_bundle=1
    else
        RESP=$(curl -sS "http://127.0.0.1:$PORT/health" 2>&1)
        if echo "$RESP" | grep -q '"status":"ok"'; then
            echo "  [OK] bundle porta $PORT, /health = $RESP"
        else
            echo "  [FAIL] /health inatteso: $RESP"
            rc_bundle=1
        fi
    fi
    kill $PID 2>/dev/null
    sleep 1
    kill -9 $PID 2>/dev/null
    rm -rf "$TMP"
fi
t_bundle=$(python -c "import time;print(f'{time.time()-$t_bundle0:.1f}')")

t_tot=$(python -c "import time;print(f'{time.time()-$t0:.1f}')")

echo
sep
echo "Riepilogo"
sep
printf "  backend    : rc=%s  tempo=%ss\n" "$rc_backend" "$t_backend"
printf "  tassonomia : rc=%s  tempo=%ss\n" "$rc_tax" "$t_tax"
printf "  avversarial: rc=%s  tempo=%ss\n" "$rc_avv" "$t_avv"
printf "  matrice    : rc=%s  tempo=%ss\n" "$rc_mat" "$t_mat"
printf "  documenti  : rc=%s  tempo=%ss\n" "$rc_doc" "$t_doc"
printf "  garanzie   : rc=%s  tempo=%ss\n" "$rc_g" "$t_g"
printf "  interfaccia: rc=%s  tempo=%ss\n" "$rc_ui" "$t_ui"
printf "  bundle     : rc=%s  tempo=%ss\n" "$rc_bundle" "$t_bundle"
printf "  totale     : tempo=%ss\n" "$t_tot"
sep

if [ $rc_backend -ne 0 ] || [ $rc_tax -ne 0 ] || [ $rc_avv -ne 0 ] || \
   [ $rc_mat -ne 0 ] || [ $rc_doc -ne 0 ] || [ $rc_ui -ne 0 ] || \
   [ $rc_g -ne 0 ] || [ $rc_bundle -ne 0 ]; then
    echo "STATO: FALLITO"
    exit 1
fi
echo "STATO: OK — tutte le suite passate."
exit 0
