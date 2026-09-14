# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Avanzamento e annullamento dell'analisi in corso.

Su questa macchina il motore analizza ~2.500 caratteri al secondo: un
documento da mezzo milione di caratteri sono più di tre minuti. Nessuna
ottimizzazione toglie quel tempo — metà è inferenza del modello, ed è il
pavimento. Quindi l'operazione lunga non si evita: si rende visibile e
si rende annullabile.

Due cose, con lo stesso meccanismo:

- **avanzamento reale**: ``fatti``/``totali`` sono caratteri di questo
  documento effettivamente analizzati, non una barra che si muove da
  sola. Aggiornati dove il lavoro accade davvero.
- **annullamento**: ``annulla_analisi()`` alza una bandiera; il lavoro la
  controlla nei suoi punti caldi e solleva ``Annullato``. Non uccide un
  thread — lo fa terminare da sé, così il vault non resta a metà.

Un solo lavoro alla volta, come in ``backend.ocr``: la finestra è una e
l'utente è uno. Lo stato è globale e protetto da lock perché chi lo
legge (l'event loop che risponde al polling) non è chi lo scrive (il
thread che analizza).
"""

from __future__ import annotations

import threading


class Annullato(Exception):
    """L'utente ha chiesto di interrompere l'operazione in corso."""


_lock = threading.Lock()
_stato = {"attivo": False, "fatti": 0, "totali": 0}
_annullato = False


def inizia(totali: int) -> None:
    """Apre un lavoro di ``totali`` caratteri e azzera l'annullamento."""
    global _annullato
    with _lock:
        _annullato = False
        _stato.update(attivo=True, fatti=0, totali=max(0, totali))


def termina() -> None:
    """Chiude il lavoro. Da chiamare anche quando finisce male."""
    global _annullato
    with _lock:
        _annullato = False
        _stato.update(attivo=False, fatti=0, totali=0)


def annulla_analisi() -> None:
    """Chiede l'interruzione. Torna subito: interrompe chi sta lavorando."""
    global _annullato
    with _lock:
        _annullato = True


def stato_analisi() -> dict:
    """Copia dello stato corrente, per il polling della finestra."""
    with _lock:
        return dict(_stato)


def controlla() -> None:
    """Solleva ``Annullato`` se l'utente ha premuto Annulla.

    Va chiamata nei cicli caldi: fra un pezzo e l'altro del lavoro, non
    dentro un'operazione atomica. Fuori da un lavoro aperto non fa
    nulla, così benchmark e test possono chiamare il motore senza
    conoscere questo modulo.
    """
    with _lock:
        if _annullato:
            raise Annullato("Analisi annullata su richiesta dell'utente.")


def segna(fatti: int) -> None:
    """Registra i caratteri analizzati finora e controlla l'annullamento."""
    with _lock:
        if _annullato:
            raise Annullato("Analisi annullata su richiesta dell'utente.")
        if _stato["attivo"]:
            _stato["fatti"] = min(fatti, _stato["totali"])
