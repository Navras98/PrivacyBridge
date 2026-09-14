#!/usr/bin/env python3
# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""PrivacyBridge — Avvio dell'app desktop (macOS / Windows / Linux).

Bootstrap:
 1. determina la cartella dati utente via ``platformdirs``;
 2. individua il motore di riconoscimento incluso nel pacchetto (in
    ``<bundle>/Contents/Resources/modello/`` su macOS, in ``modello/``
    accanto all'eseguibile su Windows/Linux); imposta
    ``PRIVACYBRIDGE_MODELLO_DIR`` prima di qualsiasi import di transformers;
 3. avvia FastAPI in-process su porta libera, bind ``127.0.0.1``;
 4. apre la finestra principale (pywebview) — nessun terminale visibile.

Se il motore di riconoscimento non è presente nel pacchetto (installazione
corrotta), mostra un errore chiaro nella finestra e termina. Non tenta
alcun download: PrivacyBridge è offline per costruzione.
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


# Silenzia stdout/stderr: il bundle apre come app grafica, non deve stampare.
# Debug: settare PRIVACYBRIDGE_DEBUG=1.
_DEBUG = bool(os.environ.get("PRIVACYBRIDGE_DEBUG"))
if not _DEBUG:
    logging.disable(logging.CRITICAL)


from backend.percorsi import cartella_dati, percorso_vault

DATA_DIR = cartella_dati()
os.environ.setdefault("PRIVACYBRIDGE_DB", str(percorso_vault()))
LOG_FILE = DATA_DIR / "log.txt"


def _log(msg: str) -> None:
    """Scrive una riga di log su file dentro la cartella dati utente.

    Attivato sempre: il log del primo avvio serve al post-mortem anche
    se ``PRIVACYBRIDGE_DEBUG`` non è settato.
    """
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except OSError:
        # Cartella non scrivibile o disco pieno: l'app parte lo stesso.
        # Un log che impedisce l'avvio è peggio di un avvio senza log.
        pass
    if _DEBUG:
        print(msg, flush=True)


def _trova_porta() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _avvia_api(porta: int) -> None:
    import uvicorn

    from api.main import app

    uvicorn.run(app, host="127.0.0.1", port=porta, log_level="critical")


def _attendi_health(base: str, timeout_s: float = 60.0) -> bool:
    scadenza = time.time() + timeout_s
    while time.time() < scadenza:
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.1)
    return False


# ---------------------------------------------------------------------------
# Localizzazione del motore di riconoscimento
# ---------------------------------------------------------------------------
#
# Strategia di ricerca (in ordine):
#   1. Override esplicito via ``PRIVACYBRIDGE_MODELLO_DIR``.
#   2. Bundle ``.app`` — quattro casi coprono tutti gli scenari reali:
#      2a. ``avvio.py`` è DENTRO un ``.app`` (PyInstaller/production):
#          risalgo da ``__file__`` fino a un parent con suffix ``.app``.
#      2b. ``sys.executable`` è dentro un ``.app`` (idem): risalgo da lì.
#      2c. ``avvio.py`` è SORELLA del bundle (setup di sviluppo attuale,
#          in cui il launcher shell fa ``cd`` alla cartella progetto e
#          lancia ``avvio.py`` da lì): cerco ``./PrivacyBridge.app/…``
#          nella CWD e in ``HERE``.
#      2d. Windows/Linux — ``modello/`` accanto all'eseguibile/avvio.py.
#   3. Fallback cache HuggingFace: se il modello è già stato scaricato
#      (utente che ha usato una versione precedente), lo usiamo così
#      l'app parte comunque. Documentato come "installazione parziale".
#
# Se nulla funziona, l'errore riporta l'ELENCO dei percorsi tentati per
# permettere una diagnostica immediata all'utente.


_MODELLO_MARKERS = ("config.json", "tokenizer.json", "model.safetensors")

APP_NAME_BUNDLE = "PrivacyBridge.app"


def _valida_modello(cartella: Path) -> bool:
    if not cartella.is_dir():
        return False
    for marker in _MODELLO_MARKERS:
        if not (cartella / marker).is_file():
            return False
    return True


def _candidati_percorsi_modello() -> list[Path]:
    """Restituisce tutti i percorsi candidati (in ordine) — validi e non.

    Il caller dovrà filtrare con ``_valida_modello``. Esporre la lista
    completa permette di stamparla nel messaggio d'errore quando nessuno
    funziona.
    """
    candidati: list[Path] = []

    # 1. Override esplicito.
    env = os.environ.get("PRIVACYBRIDGE_MODELLO_DIR")
    if env:
        candidati.append(Path(env))

    # 2a. avvio.py dentro un .app (production PyInstaller).
    for parent in [HERE] + list(HERE.parents):
        if parent.suffix == ".app":
            candidati.append(parent / "Contents" / "Resources" / "modello")
            break

    # 2b. sys.executable dentro un .app.
    exe = Path(sys.executable).resolve()
    for parent in [exe] + list(exe.parents):
        if parent.suffix == ".app":
            candidati.append(parent / "Contents" / "Resources" / "modello")
            break

    # 2c. Bundle costruito accanto al sorgente, non attorno ad esso: in
    #     sviluppo ``avvio.py`` sta in ``src/`` e il bundle in ``build/``.
    #     Tento la radice del progetto, la CWD (il launcher shell fa cd
    #     al progetto) e HERE, per coprire anche installazioni piatte.
    for base in (HERE.parent / "build", Path.cwd() / "build", Path.cwd(), HERE):
        candidati.append(base / APP_NAME_BUNDLE / "Contents" / "Resources" / "modello")

    # 2d. Windows/Linux: cartella accanto all'eseguibile/script.
    candidati.append(HERE / "modello")
    candidati.append(exe.parent / "modello")

    return candidati


def _trova_modello_nel_pacchetto() -> Path | None:
    """Ritorna il primo percorso candidato valido, oppure ``None``.

    Il caller a valle deve chiamare ``_trova_modello_hf_cache`` come
    ripiego prima di dichiarare fallimento.
    """
    for c in _candidati_percorsi_modello():
        if _valida_modello(c):
            return c
    return None


def _trova_modello_hf_cache() -> Path | None:
    """Ripiego: usa la cache HuggingFace se contiene la revisione
    fissata del modello.

    Non è la strada preferita (l'app dovrebbe essere autonoma con il
    modello nel bundle), ma se l'utente ha già scaricato il modello con
    una versione precedente evitare l'errore migliora l'esperienza.
    """
    try:
        from huggingface_hub import scan_cache_dir

        from backend.motore_neurale import _MODEL_ID, _MODEL_REVISION
    except Exception:
        return None
    try:
        cache = scan_cache_dir()
    except Exception:
        return None
    for repo in cache.repos:
        if repo.repo_id != _MODEL_ID:
            continue
        for rev in repo.revisions:
            if rev.commit_hash.startswith(_MODEL_REVISION):
                # snapshot_path è la cartella con i link ai blob.
                snapshot = getattr(rev, "snapshot_path", None)
                if snapshot and _valida_modello(Path(snapshot)):
                    return Path(snapshot)
    return None


def _mostra_errore_modello_mancante(webview_module, percorsi_tentati: list[Path]) -> None:
    """Finestra minimale che spiega all'utente cosa è successo.

    L'elenco dei percorsi tentati compare in ``<pre>`` — permette a
    utente/supporto di capire dove il bundle è stato piazzato in modo
    non standard.
    """
    import html as _html

    elenco = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(percorsi_tentati))
    testo_pre = _html.escape(elenco)

    tmpl = """<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">
<title>PrivacyBridge — Errore</title>
<style>
:root {
  --grafite:#1E2126; --zinco:#CFD5DB; --foglio:#FBFBFA; --ceralacca:#8E1F3F;
}
html,body{height:100%;margin:0;background:var(--zinco);color:var(--grafite);
  font-family:-apple-system,"Segoe UI Variable","Segoe UI",system-ui,sans-serif;}
.box{padding:28px 32px;height:100%;box-sizing:border-box;display:flex;
  flex-direction:column;gap:10px;overflow:auto;}
h1{margin:0;font-family:ui-serif,"New York",Cambria,Georgia,serif;
  font-size:20px;color:var(--ceralacca);}
p{margin:0;font-size:14px;line-height:1.5;}
pre{background:var(--foglio);border:1px solid #a9b0b8;border-radius:4px;
  padding:8px 10px;margin:6px 0 0;font-family:ui-monospace,"SF Mono",
  Consolas,monospace;font-size:11.5px;overflow:auto;max-height:220px;}
code{font-family:ui-monospace,"SF Mono","Cascadia Code",Consolas,monospace;
  font-size:12px;background:var(--foglio);padding:2px 6px;border-radius:3px;
  border:1px solid #a9b0b8;}
</style></head><body><div class="box">
<h1>Installazione incompleta</h1>
<p>PrivacyBridge non trova il motore di riconoscimento. Ha cercato la
cartella <code>modello</code> in questi percorsi:</p>
<pre>__PERCORSI__</pre>
<p>Reinstalla l'applicazione scaricando di nuovo il pacchetto
completo, oppure ripristina la cartella <code>modello</code>
dall'archivio di installazione.</p>
<p>Log dettagliato: <code>__LOG__</code></p>
</div></body></html>"""
    html_full = tmpl.replace("__PERCORSI__", testo_pre).replace(
        "__LOG__", _html.escape(str(LOG_FILE))
    )

    webview_module.create_window(
        title="PrivacyBridge",
        html=html_full,
        width=620,
        height=380,
        resizable=True,
    )
    webview_module.start()


def _apri_finestra_principale(webview_module, porta: int) -> None:
    webview_module.create_window(
        title="PrivacyBridge",
        url=f"http://127.0.0.1:{porta}",
        width=1400,
        height=900,
        min_size=(1000, 700),
        resizable=True,
    )
    # private_mode=True (il default) azzera localStorage a ogni chiusura:
    # la scelta del tema chiaro/scuro non sopravviverebbe al riavvio.
    webview_module.start(
        private_mode=False,
        storage_path=str(DATA_DIR / "webview"),
    )


def main() -> int:
    _log("=" * 50)
    _log(f"avvio.py start (data_dir={DATA_DIR})")

    # Offline duro: imposta PRIMA di importare qualunque cosa che possa
    # toccare la rete (transformers/huggingface_hub leggono queste env var
    # a import-time).
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    modello = _trova_modello_nel_pacchetto()
    origine = "bundle"
    if modello is None:
        # Ripiego: cache HuggingFace se disponibile.
        modello = _trova_modello_hf_cache()
        origine = "cache huggingface"

    if modello is None:
        percorsi = _candidati_percorsi_modello()
        _log(
            "motore di riconoscimento non trovato. Percorsi tentati:\n"
            + "\n".join(f"  - {p}" for p in percorsi)
        )
        import webview
        _mostra_errore_modello_mancante(webview, percorsi)
        return 3

    os.environ["PRIVACYBRIDGE_MODELLO_DIR"] = str(modello)
    _log(f"motore di riconoscimento ({origine}): {modello}")

    porta = _trova_porta()
    _log(f"avvio api su porta {porta}")
    threading.Thread(target=_avvia_api, args=(porta,), daemon=True).start()

    if not _attendi_health(f"http://127.0.0.1:{porta}"):
        _log("timeout /health: esco")
        return 2

    # Controllo aggiornamenti in background (FASE 4). Non blocca l'apertura
    # della finestra; il timeout di rete è 3s. Se disattivato, esce subito.
    try:
        from backend.aggiornamenti import controlla_in_background
        controlla_in_background()
        _log("check aggiornamenti avviato")
    except Exception as exc:
        _log(f"check aggiornamenti non avviato: {exc}")

    _log("apertura finestra principale")
    import webview
    _apri_finestra_principale(webview, porta)
    _log("finestra chiusa: uscita ordinata")
    return 0


if __name__ == "__main__":
    sys.exit(main())
