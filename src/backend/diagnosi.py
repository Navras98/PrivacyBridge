# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Modalità diagnostica della pipeline di anonimizzazione.

Attivazione:
  - variabile d'ambiente ``PRIVACYBRIDGE_DIAGNOSI=1`` (stampa su stderr), o
  - ``anonimizza(..., diagnosi=True)`` e poi ``ultima_diagnosi()``.

Per ogni candidato registra il percorso completo: chi l'ha rilevato,
con che punteggio, quali filtri l'hanno esaminato e dove (e perché) è
stato scartato. Registra anche i token del testo che sono nomi noti ma
non sono mai diventati candidati (es. minuscoli non ricapitalizzati):
è il caso più difficile da capire dall'esterno.

Uso da terminale:
    echo "ciao sono andrea, viene marco con me" | \
        PRIVACYBRIDGE_DIAGNOSI=1 venv/bin/python -m backend.motore anonimizza
"""

from __future__ import annotations

import os
import re
import sys
import threading

_lock = threading.Lock()
_eventi: list[dict] = []


def attiva_da_env() -> bool:
    return bool(os.environ.get("PRIVACYBRIDGE_DIAGNOSI"))


class Tracer:
    """Raccoglie gli eventi della pipeline per un'esecuzione."""

    def __init__(self, attiva: bool):
        self.attiva = attiva
        self.eventi: list[dict] = []

    def ev(self, fase: str, dettaglio: str, span: str = "",
           tipo: str = "", score: float | None = None) -> None:
        if not self.attiva:
            return
        e = {"fase": fase, "dettaglio": dettaglio, "span": span,
             "tipo": tipo, "score": score}
        self.eventi.append(e)
        if attiva_da_env():
            s = f"[diagnosi] {fase:<22s}"
            if span:
                s += f" {span!r}"
            if tipo:
                s += f" [{tipo}"
                if score is not None:
                    s += f" {score:.2f}"
                s += "]"
            s += f" — {dettaglio}"
            print(s, file=sys.stderr)

    def candidato(self, r, testo: str, origine: str) -> None:
        """Registra un candidato emesso da un recognizer."""
        self.ev("rilevato", f"da {origine}", testo[r.start:r.end],
                r.entity_type, r.score)

    def scartato(self, r, testo: str, filtro: str, motivo: str) -> None:
        self.ev(f"scartato:{filtro}", motivo, testo[r.start:r.end],
                r.entity_type, r.score)

    def accettato(self, valore: str, tipo: str, placeholder: str) -> None:
        self.ev("accettato", f"→ {placeholder}", valore, tipo)

    # ------------------------------------------------------------------
    # Token mai diventati candidati (nomi noti persi a monte)
    # ------------------------------------------------------------------

    _PAROLA_RE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ']{2,29}")

    def analizza_token_persi(self, testo_analisi: str,
                             span_candidati: set[tuple[int, int]]) -> None:
        """Per ogni token che è un nome/cognome noto ma NON è coperto da
        alcun candidato, spiega perché non è mai entrato in pipeline."""
        if not self.attiva:
            return
        from .nomi_italiani import (
            _FORMULE_ESCLUSE,
            _VOCAB_IT,
            _cognome_noto,
            _nome_ambiguo,
            _nome_noto,
        )
        for m in self._PAROLA_RE.finditer(testo_analisi):
            lc = m.group(0).lower()
            if not (_nome_noto(lc) or _cognome_noto(lc)):
                continue
            coperto = any(s <= m.start() and m.end() <= e
                          for s, e in span_candidati)
            if coperto:
                continue
            motivi = []
            if lc in _FORMULE_ESCLUSE:
                motivi.append("formula esclusa (saluto/titolo)")
            if m.group(0)[0].islower():
                motivi.append("minuscolo: mai diventato candidato maiuscolo")
                if lc in _VOCAB_IT:
                    motivi.append(
                        "in vocab_it_60k → il truecasing non lo ricapitalizza"
                    )
            if _nome_noto(lc) and _nome_ambiguo(lc):
                motivi.append("marcato AMBIGUO nel TSV (serve contesto forte)")
            elif _cognome_noto(lc) and not _nome_noto(lc):
                motivi.append("solo-cognome (da solo serve contesto forte)")
            self.ev(
                "token perso",
                "; ".join(motivi) or "nessun recognizer lo ha emesso",
                m.group(0),
            )


def registra(eventi: list[dict]) -> None:
    global _eventi
    with _lock:
        _eventi = list(eventi)


def ultima_diagnosi() -> list[dict]:
    """Eventi dell'ultima ``anonimizza`` eseguita con diagnosi attiva."""
    with _lock:
        return list(_eventi)
