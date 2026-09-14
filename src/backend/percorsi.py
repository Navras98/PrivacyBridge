# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Percorsi delle cartelle di PrivacyBridge.

Due famiglie che non vanno confuse. Le *risorse* — le liste di nomi,
cognomi e comuni — stanno accanto al codice e viaggiano dentro il
pacchetto. I *dati dell'utente* — il vault — stanno nella cartella di
sistema, dove un aggiornamento dell'applicazione non li tocca.

Determina a runtime — via ``platformdirs`` — la cartella dati corretta per
il sistema operativo, così l'app non scrive mai nel proprio bundle e resta
portabile tra macOS e Windows senza percorsi hardcoded.

macOS  → ~/Library/Application Support/PrivacyBridge
Windows → %APPDATA%\\PrivacyBridge
Linux  → ~/.local/share/PrivacyBridge

Override esplicito via ``PRIVACYBRIDGE_DATA_DIR`` (per test o profili
condivisi). Il file del vault SQLite è ``<data_dir>/vault.db`` a meno che
``PRIVACYBRIDGE_DB`` non punti a un altro file.
"""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "PrivacyBridge"


def cartella_liste() -> Path:
    """Cartella delle liste di nomi, cognomi, comuni e vocabolario.

    Risorsa dell'applicazione, non dato dell'utente: sta accanto al
    codice e viene copiata dentro il pacchetto. Il percorso è calcolato
    una volta sola qui perché tre moduli lo usano, e tre copie della
    stessa espressione si rompono in silenzio appena si sposta una
    cartella.
    """
    return Path(__file__).resolve().parent.parent / "data" / "liste"


def cartella_dati() -> Path:
    """Restituisce la cartella dati utente, creandola se assente.

    Permessi 0700: dentro finisce il vault, che contiene i valori
    originali in chiaro. Su una macchina con più account il default
    0755 li lascerebbe elencabili dagli altri utenti.
    """
    override = os.environ.get("PRIVACYBRIDGE_DATA_DIR")
    if override:
        p = Path(override)
    else:
        p = Path(user_data_dir(APP_NAME, appauthor=False))
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    return p


def percorso_vault() -> Path:
    """Path del file SQLite del vault. Rispetta ``PRIVACYBRIDGE_DB``."""
    override = os.environ.get("PRIVACYBRIDGE_DB")
    if override:
        p = Path(override)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    return cartella_dati() / "vault.db"
