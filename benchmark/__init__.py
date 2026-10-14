# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Misure sui documenti veri dell'utente e sulle prestazioni dell'app.

Non fa parte di ciò che viene consegnato: serve a stabilire, con numeri
riproducibili, quanto il motore trova davvero e quanto ci mette.

Riproducibili a una condizione: che la misura non guardi la cartella dati
dell'utente.  Lì stanno ``impostazioni.json`` — con l'elenco delle
categorie accese — e la rubrica personale, e l'utente li cambia mentre
lavora, dall'interfaccia.  Un benchmark che li legge misura la
configurazione di stamattina, non il motore; due esecuzioni a distanza di
un giorno danno numeri diversi senza che nessuno abbia toccato il codice.

È già successo: la stessa cartella di documenti ha dato 141 sostituzioni
il 1 agosto alle 11:41 e 616 lo stesso pomeriggio, perché nel frattempo
l'utente aveva acceso tutte le categorie dall'app.

``isola()`` sposta la cartella dati in una temporanea e va chiamata
**prima** di importare qualunque cosa da ``backend``.  Restituisce anche
il percorso del vault, e va usato quello: un vault fuori dalla cartella
isolata sopravvive alle esecuzioni e ricicla le corrispondenze
valore→segnaposto della volta prima.  Anche questo è già successo — con
il vault vecchio ``Comune di Rimini`` continuava a uscire come LUOGO
dopo che il codice era stato corretto per emetterlo come ORG, e il
guadagno reale del recognizer restava invisibile.
"""

from __future__ import annotations

import os
from pathlib import Path

# Categorie accese per difetto nella versione consegnata. Ripetute qui e
# non importate da backend.motore perché isola() gira prima di qualsiasi
# import del backend, ed è proprio quello il punto.
CATEGORIE_CONSEGNA: frozenset[str] = frozenset({
    "PERSONA", "EMAIL", "TELEFONO", "IBAN", "CF", "PIVA", "CARTA", "CAP",
    "INDIRIZZO", "SANITARIO", "DOCUMENTO", "DATA_NASCITA", "LUOGO_NASCITA",
    "TARGA", "VIN", "PRATICA", "SOCIAL",
})


def isola(nome: str) -> Path:
    """Punta la cartella dati a ``/tmp/pb_bench_<nome>/``, vuota.

    Ritorna il percorso, così chi chiama può ispezionarlo. Da invocare in
    cima al modulo, prima degli import di ``backend``.
    """
    dati = Path(os.environ.get("PRIVACYBRIDGE_BENCH_DIR", f"/tmp/pb_bench_{nome}"))
    if dati.exists():
        for f in dati.iterdir():
            if f.is_file():
                f.unlink()
    dati.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.environ["PRIVACYBRIDGE_DATA_DIR"] = str(dati)
    os.environ["PRIVACYBRIDGE_DB"] = str(dati / "vault.db")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    return dati


def vault_isolato(nome: str) -> str:
    """Percorso del vault dentro la cartella isolata, da passare a ``anonimizza``.

    ``anonimizza(db_path=...)`` ignora ``PRIVACYBRIDGE_DB``: chi passa il
    percorso a mano deve passare *questo*, altrimenti il vault resta fuori
    dalla cartella che ``isola()`` svuota e la misura eredita lo stato di
    ieri.
    """
    return str(isola(nome) / "vault.db")
