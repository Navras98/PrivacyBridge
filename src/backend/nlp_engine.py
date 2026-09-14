# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Setup del motore NLP di Presidio.

Fornisce:
 - ``build_analyzer()``: crea un ``AnalyzerEngine`` italiano+inglese con spaCy
   ``it_core_news_lg`` / ``en_core_web_lg``, i recognizer standard di Presidio
   e i recognizer italiani custom, più il motore neurale PII italiano.
 - ``build_neural_recognizer()``: costruisce il recognizer neurale.
   Vedi ``backend.motore_neurale``.

``build_analyzer`` accetta un parametro ``motore`` in {"rizzo", "none"} per
scegliere se attivare il modello neurale (utile in test e benchmark).
"""

from __future__ import annotations

import logging

from presidio_analyzer import (
    AnalyzerEngine,
    RecognizerRegistry,
)
from presidio_analyzer.nlp_engine import NlpEngineProvider

from .motore_neurale import build_neural_recognizer
from .nomi_italiani import build_nome_italiano_recognizer
from .recognizers import custom_italian_recognizers
from .rubrica import build_rubrica_recognizer

logger = logging.getLogger("privacybridge.nlp")


# Modelli spaCy di default (già scaricati nell'ambiente).
_SPACY_CONFIG = {
    "nlp_engine_name": "spacy",
    "models": [
        {"lang_code": "it", "model_name": "it_core_news_lg"},
        {"lang_code": "en", "model_name": "en_core_web_lg"},
    ],
}


# ---------------------------------------------------------------------------
# AnalyzerEngine
# ---------------------------------------------------------------------------

def build_analyzer(
    motore: str = "rizzo",
    supported_languages: list[str] | None = None,
) -> AnalyzerEngine:
    """Costruisce un ``AnalyzerEngine`` con spaCy, recognizer standard e custom.

    ``motore``:
     - ``"rizzo"``: rizzo-pii-0.3B come modello neurale (default).
     - ``"none"``: solo spaCy + regex, nessun modello neurale specifico PII
       (utile in test veloci e nei benchmark che vogliono isolare l'apporto
       del modello neurale).
    """

    langs = supported_languages or ["it", "en"]

    nlp_engine = NlpEngineProvider(nlp_configuration=_SPACY_CONFIG).create_engine()

    registry = RecognizerRegistry(supported_languages=langs)
    registry.load_predefined_recognizers(languages=langs, nlp_engine=nlp_engine)

    for rec in custom_italian_recognizers():
        registry.add_recognizer(rec)

    # Recognizer dizionario nomi italiani (colloquiali, 3 livelli — FASE 2).
    nome_it = build_nome_italiano_recognizer()
    if nome_it is not None:
        registry.add_recognizer(nome_it)

    # Recognizer rubrica personale (FASE 2.3): priorità assoluta.
    rubrica = build_rubrica_recognizer()
    if rubrica is not None:
        registry.add_recognizer(rubrica)

    if motore == "rizzo":
        neural_rec = build_neural_recognizer()
        if neural_rec is not None:
            neural_rec.supported_language = "it"
            registry.add_recognizer(neural_rec)
            # Il modello neurale è italiano-only; per "en" restano spaCy
            # en_core_web_lg + i recognizer standard di Presidio.

    analyzer = AnalyzerEngine(
        nlp_engine=nlp_engine,
        registry=registry,
        supported_languages=langs,
    )
    return analyzer
