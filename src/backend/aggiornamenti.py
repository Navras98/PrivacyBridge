# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Controllo aggiornamenti opt-out (FASE 4).

Regole (vedi DECISIONI.md):
 - controllo silenzioso all'avvio, in thread separato;
 - timeout breve, mai bloccante;
 - mai autoupdate, solo avviso + link;
 - disattivabile via impostazione persistente in ``<data_dir>/
   impostazioni.json``.

L'unico traffico di rete generato da questo modulo è: una GET al
``VERSIONE_URL`` (default GitHub Pages) con timeout 3s. Se fallisce
per QUALSIASI motivo, silenzio.

Il formato del JSON remoto atteso:
    {
      "versione":       "1.1.0",
      "data":           "2026-08-15",
      "note":           "Testo breve di rilascio",
      "url_download":   "https://.../PrivacyBridge-1.1.0.dmg"
    }
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.request
from pathlib import Path

from .percorsi import cartella_dati

logger = logging.getLogger("privacybridge.aggiornamenti")


VERSIONE_CORRENTE = "1.0.0"

# URL configurabile. Il default punta a un file mantenuto dall'autore su
# GitHub Pages. Il valore può essere sovrascritto per test/mirror via
# variabile ambiente ``PRIVACYBRIDGE_URL_VERSIONE``.
_URL_DEFAULT = "https://andreasforna.github.io/privacybridge/versione.json"


def _url_versione() -> str:
    import os
    return os.environ.get("PRIVACYBRIDGE_URL_VERSIONE", _URL_DEFAULT)


# ---------------------------------------------------------------------------
# Impostazioni persistenti
# ---------------------------------------------------------------------------

def _percorso_impostazioni() -> Path:
    return cartella_dati() / "impostazioni.json"


def _leggi_impostazioni() -> dict:
    p = _percorso_impostazioni()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        # File corrotto → riparto vuoto (l'utente non lo modifica a mano).
        return {}


def _scrivi_impostazioni(dati: dict) -> None:
    p = _percorso_impostazioni()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(dati, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def check_aggiornamenti_attivo() -> bool:
    """True se l'utente non ha disabilitato il controllo. Default: True."""
    return bool(_leggi_impostazioni().get("check_aggiornamenti", True))


def imposta_check_aggiornamenti(attivo: bool) -> None:
    dati = _leggi_impostazioni()
    dati["check_aggiornamenti"] = bool(attivo)
    _scrivi_impostazioni(dati)


# ---------------------------------------------------------------------------
# Confronto versione (SemVer semplice)
# ---------------------------------------------------------------------------

def _parse_versione(v: str) -> tuple[int, int, int]:
    parts = (v or "").strip().split(".")
    try:
        maj = int(parts[0]) if len(parts) > 0 else 0
        min_ = int(parts[1]) if len(parts) > 1 else 0
        pat = int(parts[2]) if len(parts) > 2 else 0
        return (maj, min_, pat)
    except (ValueError, IndexError):
        return (0, 0, 0)


def _piu_recente(a: str, b: str) -> bool:
    """True se ``a`` è strettamente più recente di ``b``."""
    return _parse_versione(a) > _parse_versione(b)


# ---------------------------------------------------------------------------
# Fetch remoto
# ---------------------------------------------------------------------------

def _fetch_versione_remota(timeout: float = 3.0) -> dict | None:
    """Chiama l'URL versione con timeout breve. None se fallisce."""
    try:
        req = urllib.request.Request(
            _url_versione(),
            headers={"User-Agent": f"PrivacyBridge/{VERSIONE_CORRENTE}"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            body = resp.read().decode("utf-8", errors="replace")
        dati = json.loads(body)
        if not isinstance(dati, dict):
            return None
        # Sanità minima: deve avere il campo versione.
        if "versione" not in dati or not isinstance(dati["versione"], str):
            return None
        return dati
    except Exception as exc:
        logger.debug("Fetch versione fallito (silente): %s", exc)
        return None


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

_STATO_LOCK = threading.Lock()
_STATO: dict = {
    "ultimo_check": None,      # ISO string
    "nuova_versione": None,    # dict o None
}


def controlla_in_background() -> threading.Thread:
    """Avvia il controllo aggiornamenti in un thread daemon. Non blocca.
    Se ``check_aggiornamenti`` è False, il thread esce immediatamente.
    """
    def _worker():
        if not check_aggiornamenti_attivo():
            return
        remoto = _fetch_versione_remota()
        with _STATO_LOCK:
            _STATO["ultimo_check"] = _iso_now()
            if remoto and _piu_recente(remoto.get("versione", ""), VERSIONE_CORRENTE):
                _STATO["nuova_versione"] = remoto
            else:
                _STATO["nuova_versione"] = None

    t = threading.Thread(target=_worker, daemon=True, name="check_aggiornamenti")
    t.start()
    return t


def stato_aggiornamento() -> dict:
    """Ritorna lo stato corrente, safe per JSON."""
    with _STATO_LOCK:
        return {
            "versione_corrente": VERSIONE_CORRENTE,
            "check_attivo": check_aggiornamenti_attivo(),
            "ultimo_check": _STATO["ultimo_check"],
            "nuova_versione": _STATO["nuova_versione"],
        }


def _iso_now() -> str:
    import datetime
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
