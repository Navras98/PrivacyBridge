# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Recognizer per la rubrica personale (FASE 2.3).

La rubrica è un dizionario dell'utente: nomi di clienti, aziende,
codici cliente, prodotti — qualunque termine che deve essere
riconosciuto ogni volta.

I termini della rubrica hanno priorità assoluta: la sostituzione
avviene sempre, indipendentemente dal contesto o dalla presenza in
altri dizionari.

Il recognizer viene ricostruito ogni volta che si carica l'analyzer:
è una scelta consapevole. La rubrica cresce lentamente (decine, forse
centinaia di voci per uno studio), non serve reload dinamico. Il costo
di ricaricare l'analyzer dopo un import CSV pesante è nell'ordine dei
secondi, accettabile.
"""

from __future__ import annotations

import logging
import re

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from .percorsi import percorso_vault
from .vault import Vault

logger = logging.getLogger("privacybridge.rubrica")


class RubricaRecognizer(EntityRecognizer):
    """Emette entità per ogni termine della rubrica trovato nel testo.

    Match case-insensitive, ma la sostituzione preserva la case
    originale del testo (l'entity mantiene lo span originale, non il
    testo della rubrica).
    """

    def __init__(self, termini: list[tuple[str, str]]):
        """``termini`` è una lista di tuple ``(testo, tipo)``."""
        # Ordino dai più lunghi ai più corti: così su match sovrapposti
        # ("Mario Rossi" batte "Mario") il combinato vince.
        self._termini = sorted(termini, key=lambda t: -len(t[0]))
        # Compilo un'unica regex con lookaround per confini alfa: evita
        # di catturare "Mario" dentro "Mariotti".
        self._pattern = None
        if self._termini:
            escaped = [re.escape(t[0]) for t in self._termini]
            self._pattern = re.compile(
                r"(?<![A-Za-zÀ-ÿ0-9_])"
                + r"(?:" + "|".join(escaped) + r")"
                + r"(?![A-Za-zÀ-ÿ0-9_])",
                re.IGNORECASE,
            )
            self._tipo_per_lc = {t.lower(): tp for t, tp in self._termini}

        super().__init__(
            supported_entities=list({tp for _, tp in self._termini}) or ["ALTRO"],
            supported_language="it",
            name="RubricaRecognizer",
        )

    def load(self) -> None:  # pragma: no cover
        return None

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        if not text or self._pattern is None:
            return []
        risultati: list[RecognizerResult] = []
        for m in self._pattern.finditer(text):
            catturato = m.group(0)
            tipo = self._tipo_per_lc.get(catturato.lower(), "ALTRO")
            risultati.append(
                RecognizerResult(
                    entity_type=tipo,
                    start=m.start(),
                    end=m.end(),
                    # Score massimo: la rubrica è autoritativa.
                    score=1.0,
                )
            )
        return risultati


def _leggi_termini_rubrica(db_path: str | None = None) -> set[str]:
    """Ritorna l'insieme dei termini in rubrica (minuscoli, strip).

    Usato dal motore per esentare le voci di rubrica dal filtro
    categoria: se un valore è in rubrica, deve essere sostituito
    indipendentemente da quali categorie sono attive.
    """
    try:
        vault = Vault(db_path or str(percorso_vault()))
    except Exception:
        return set()
    try:
        righe = vault.rubrica_all()
    finally:
        vault.close()
    return {r["testo"].strip().lower() for r in righe if r["testo"].strip()}


def build_rubrica_recognizer(db_path: str | None = None) -> RubricaRecognizer | None:
    """Costruisce il recognizer leggendo la rubrica dal vault.

    Ritorna ``None`` se la rubrica è vuota — così l'analyzer non
    perde tempo con un recognizer inutile.
    """
    # Percorso ricalcolato a runtime: rispetta ``PRIVACYBRIDGE_DB``
    # anche se cambia dopo l'import iniziale (utile ai test che
    # monkeypatchano l'env).
    vault = Vault(db_path or str(percorso_vault()))
    try:
        righe = vault.rubrica_all()
    finally:
        vault.close()
    termini = [(r["testo"], r["tipo"]) for r in righe if r["testo"].strip()]
    if not termini:
        return None
    logger.info("Rubrica: caricati %d termini", len(termini))
    return RubricaRecognizer(termini)
