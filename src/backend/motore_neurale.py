# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""EntityRecognizer Presidio: motore neurale PII italiano.

Modello sottostante: ``rizzoaiacademy/rizzo-pii-0.3B``.

Modello token-classification (ModernBERT, 22 tag PII italiani) usato in
sostituzione di GLiNER per le entità semantiche (PERSON, ORG, LOCATION,
DATE). I recognizer deterministici (CF, P.IVA, IBAN, ...) restano
autoritativi grazie a ``_TYPE_PRIORITY`` in ``motore._risolvi_sovrapposizioni``.

Note tecniche:
 - ``aggregation_strategy="first"`` è quella che tiene meglio insieme gli
   span multi-token (misurato: ``simple`` spezza gli indirizzi email tra
   sub-token BPE; ``max`` scarta l'ancora perché lo score dei token interni
   è basso; ``average`` idem).
 - Post-processing obbligatorio: strip whitespace/punteggiatura in coda,
   merge di span dello stesso tipo separati da <=2 caratteri (recupera i
   casi in cui il tokenizer BPE crea buchi tra parole classificate).
 - Chunking word-safe a 2000 char: il modello ha contesto 8192 token, ma
   su CPU su questa macchina l'inferenza per chunk più corto è più veloce
   in totale (input padding batch-friendly).
"""

from __future__ import annotations

import logging
import os
import re

from presidio_analyzer import (
    EntityRecognizer,
    RecognizerResult,
)
from presidio_analyzer.nlp_engine import NlpArtifacts

from . import avanzamento
from .recognizers import _cf_valido, _iban_valido, _piva_valida

logger = logging.getLogger("privacybridge.motore_neurale")


_MODEL_ID = "rizzoaiacademy/rizzo-pii-0.3B"
_MODEL_REVISION = "a7f1160d829c7b436a6d8f8ebdae523f83437edf"

# Alias retro-compatibile per script che leggevano il vecchio nome.
_MODEL_ID_DEFAULT = _MODEL_ID


# Mappa dalle label del modello ai tipi Presidio (allineati a motore._TYPE_MAP).
# Le entità già coperte da recognizer deterministici con checksum
# (CF, PIVA, IBAN, CREDITCARDNUMBER, EMAIL, TELEPHONENUM) restano mappate:
# fanno da rete di sicurezza se la regex fallisce, ma perdono nel merge
# grazie alle priorità di motore._TYPE_PRIORITY.
_RIZZO_TO_ENTITY = {
    "FULLNAME": "PERSON",
    "ORG": "ORGANIZATION",
    "STREET": "LOCATION",
    "CITY": "LOCATION",
    "PROVINCE": "LOCATION",
    "BUILDINGNUM": "LOCATION",
    "ZIPCODE": "IT_CAP",
    "DATE": "DATE_TIME",
    "TIME": "DATE_TIME",
    "EMAIL": "EMAIL_ADDRESS",
    "TELEPHONENUM": "PHONE_NUMBER",
    "IBAN": "IT_IBAN",
    "CREDITCARDNUMBER": "CREDIT_CARD",
    "CF": "IT_CODICE_FISCALE",
    "PIVA": "IT_PARTITA_IVA",
    "CATASTO": "IT_CATASTO",
    "TARGA": "IT_TARGA",
    "AMOUNT": "IT_IMPORTO",
    "DOCID": "IT_DOCUMENTO",
    "ID_DOC": "IT_DOCUMENTO",
    # GENDER e AGE vengono ignorati: da soli non sono PII e generano
    # rumore (annotazioni tipo "uomo", "35 anni").
}


class NeuralRecognizer(EntityRecognizer):
    """Wrapper Presidio per il modello neurale PII italiano (rizzo-pii-0.3B)."""

    _CHUNK_CHARS = 2000  # ~500-700 token, sicuro sotto le 512 del pipeline

    def __init__(
        self,
        pipeline,
        threshold: float = 0.5,
        supported_language: str = "it",
    ):
        self._pipeline = pipeline
        self._threshold = threshold
        supported_entities = sorted(set(_RIZZO_TO_ENTITY.values()))
        super().__init__(
            supported_entities=supported_entities,
            supported_language=supported_language,
            name="NeuralRecognizer",
        )

    def load(self) -> None:  # pragma: no cover
        return None

    def _chunks(self, text: str):
        n = len(text)
        if n <= self._CHUNK_CHARS:
            yield 0, text
            return
        i = 0
        while i < n:
            j = min(i + self._CHUNK_CHARS, n)
            if j < n:
                k = text.rfind(" ", i + self._CHUNK_CHARS // 2, j)
                if k > i:
                    j = k
            yield i, text[i:j]
            i = j

    # Caratteri che tagliamo dai bordi degli span dopo l'aggregazione BIO.
    _TRIM_CHARS = " \t\n\r.,;:!?)('\"«»"

    # Regex minimale di sanità per email/telefono; se il neurale predice
    # queste categorie ma lo span non passa il check basico, scartiamo:
    # abbiamo già i recognizer regex+checksum che coprono meglio.
    _EMAIL_SANITY = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

    def _validate_predicted_span(self, entity_type: str, value: str) -> bool:
        """Se il modello predice un tipo con validatore deterministico,
        eseguo la validazione. Questo evita falsi positivi come "IT03"
        classificato come IBAN o "0245871234" (10 cifre) classificato IBAN
        quando in realtà è un telefono. La regex+checksum in
        ``backend.recognizers`` è la fonte di verità: se rizzo la nomina
        senza rispettarla, scartiamo.
        """
        v = value.strip()
        if entity_type == "IT_CODICE_FISCALE":
            return _cf_valido(v)
        if entity_type == "IT_PARTITA_IVA":
            return v.isdigit() and _piva_valida(v)
        if entity_type == "IT_IBAN":
            return _iban_valido(v)
        if entity_type == "CREDIT_CARD":
            digits = re.sub(r"\D", "", v)
            return 12 <= len(digits) <= 19
        if entity_type == "EMAIL_ADDRESS":
            return bool(self._EMAIL_SANITY.match(v))
        if entity_type == "PHONE_NUMBER":
            digits = re.sub(r"\D", "", v)
            return 6 <= len(digits) <= 15
        return True

    def _clean_span(self, text: str, start: int, end: int):
        """Rifila whitespace e punteggiatura ai bordi. Ritorna (start,end) o None."""
        while start < end and text[start] in self._TRIM_CHARS:
            start += 1
        while end > start and text[end - 1] in self._TRIM_CHARS:
            end -= 1
        if end <= start:
            return None
        return start, end

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        results: list[RecognizerResult] = []
        if not text or not text.strip():
            return results

        # Raccolgo (start, end, entity_type, score) dopo cleanup, poi
        # eseguo un merge finale per fondere span dello stesso tipo che il
        # tokenizer BPE ha spezzato (email, indirizzi, date).
        raw_spans = []

        for offset, chunk in self._chunks(text):
            # Punto di uscita più fine che abbiamo: un chunk è ~0.7s, e
            # l'inferenza è metà del tempo totale. Fra i blocchi
            # l'attesa sarebbe di decine di secondi.
            avanzamento.controlla()
            if not chunk.strip():
                continue
            try:
                preds = self._pipeline(chunk)
            except Exception as exc:
                logger.warning("Rizzo PII inference fallita sul chunk: %s", exc)
                continue

            for p in preds:
                score = float(p.get("score", 0.0))
                if score < self._threshold:
                    continue
                raw_label = p.get("entity_group") or p.get("entity") or ""
                if raw_label.startswith(("B-", "I-")):
                    raw_label = raw_label[2:]
                entity_type = _RIZZO_TO_ENTITY.get(raw_label)
                if not entity_type:
                    continue
                if entities and entity_type not in entities:
                    continue
                start = int(p["start"]) + offset
                end = int(p["end"]) + offset
                if end <= start:
                    continue
                cleaned = self._clean_span(text, start, end)
                if cleaned is None:
                    continue
                raw_spans.append((cleaned[0], cleaned[1], entity_type, score))

        # Merge: span dello stesso tipo separati da <=2 char (che nel testo
        # non contengono caratteri "duri") vengono fusi. Riduce la
        # frammentazione degli span email/indirizzo prodotta dal BPE.
        raw_spans.sort(key=lambda t: (t[0], t[1]))
        merged = []
        for s, e, et, sc in raw_spans:
            if merged and merged[-1][2] == et and s - merged[-1][1] <= 2:
                gap = text[merged[-1][1]:s]
                # Fondiamo solo se il gap è "safe" (spazio/punteggiatura leggera).
                if all(ch in " \t.-_@" for ch in gap):
                    prev_s, _, _, prev_sc = merged[-1]
                    merged[-1] = (prev_s, e, et, max(prev_sc, sc))
                    continue
            merged.append((s, e, et, sc))

        for s, e, et, sc in merged:
            if not self._validate_predicted_span(et, text[s:e]):
                continue
            results.append(
                RecognizerResult(
                    entity_type=et,
                    start=s,
                    end=e,
                    score=max(0.4, min(0.95, sc)),
                )
            )
        return results


def _percorso_modello_locale() -> str | None:
    """Ritorna il percorso di una cartella locale contenente i file del
    motore di riconoscimento (config.json, model.safetensors, tokenizer…)
    se disponibile, altrimenti ``None``.

    Ordine di ricerca:
      1. Variabile d'ambiente ``PRIVACYBRIDGE_MODELLO_DIR`` (override).
      2. ``PrivacyBridge.app/Contents/Resources/modello/`` — dove il
         packaging (FASE 7) mette i file, così l'app è autonoma e non
         scarica nulla al primo avvio.
    """
    override = os.environ.get("PRIVACYBRIDGE_MODELLO_DIR")
    if override:
        p = os.path.abspath(override)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "config.json")):
            return p
    return None


def stato_modello() -> dict:
    """Ritorna lo stato del modello neurale senza caricarlo.

    Utile per diagnostica e per l'endpoint /health: dice dove si trova
    il modello, se è disponibile e quale revisione è attesa.
    """
    import os as _os

    info: dict = {
        "model_id": _MODEL_ID,
        "revision": _MODEL_REVISION,
        "sorgente": None,
        "disponibile": False,
        "dettaglio": "",
    }
    locale = _percorso_modello_locale()
    if locale:
        info["sorgente"] = "bundle"
        info["disponibile"] = True
        info["dettaglio"] = locale
        return info
    # Cache HuggingFace
    try:
        from huggingface_hub import try_to_load_from_cache  # type: ignore
        cached = try_to_load_from_cache(_MODEL_ID, "config.json", revision=_MODEL_REVISION)
        if cached is not None:
            info["sorgente"] = "cache"
            info["disponibile"] = True
            info["dettaglio"] = str(cached)
            return info
    except ImportError:
        pass
    except Exception:
        pass
    # Fallback: controlla se la cartella cache esiste
    cache_dir = _os.path.expanduser("~/.cache/huggingface/hub")
    safe_id = _MODEL_ID.replace("/", "--")
    if _os.path.isdir(_os.path.join(cache_dir, f"models--{safe_id}")):
        info["sorgente"] = "cache"
        info["disponibile"] = True
        info["dettaglio"] = "cache HF presente (revisione non verificata)"
        return info
    info["sorgente"] = "download"
    info["dettaglio"] = "richiederà download al primo avvio (~1.1 GB)"
    return info


def build_neural_recognizer(
    model_id: str = _MODEL_ID,
    revision: str = _MODEL_REVISION,
    threshold: float = 0.5,
    device: str | None = None,
) -> NeuralRecognizer | None:
    """Costruisce il recognizer. Ritorna ``None`` se il caricamento fallisce.

    Se ``_percorso_modello_locale()`` trova una cartella con i pesi già
    presenti (caso app distribuita con modello nel bundle), la usa
    direttamente e non contatta HuggingFace. Altrimenti tenta la cache HF
    in modalità offline, e come ultima risorsa il download.

    Se il modello non è disponibile, l'app resta funzionante: i recognizer
    deterministici (CF, P.IVA, IBAN, email, telefono…) e il dizionario
    nomi/cognomi continuano a lavorare.  Solo il rilevamento neurale di
    nomi isolati e luoghi generici degrada.
    """

    # Provo prima offline: se il modello è già disponibile, niente rete.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    try:
        from transformers import (
            AutoModelForTokenClassification,
            AutoTokenizer,
            pipeline,
        )
    except Exception as exc:
        logger.warning("transformers non disponibile: %s", exc)
        return None

    modello_locale = _percorso_modello_locale()

    def _try_load(source: str, extra: dict):
        tokenizer = AutoTokenizer.from_pretrained(source, **extra)
        model = AutoModelForTokenClassification.from_pretrained(source, **extra)
        # device=-1 forza CPU; su questa macchina MPS è rotto (0 entità/OOM).
        dev = -1 if device is None else device
        return pipeline(
            "token-classification",
            model=model,
            tokenizer=tokenizer,
            aggregation_strategy="first",
            device=dev,
        )

    # Caso 1 — modello locale nel bundle: carico da lì e chiudo.
    if modello_locale:
        try:
            pipe = _try_load(modello_locale, {})
            logger.info("Motore caricato da bundle locale: %s", modello_locale)
            return NeuralRecognizer(pipeline=pipe, threshold=threshold)
        except Exception as exc:
            logger.warning(
                "Load da bundle locale (%s) fallito: %s. Tento cache HF.",
                modello_locale, exc,
            )

    # Caso 2 — cache HuggingFace (offline).
    try:
        pipe = _try_load(model_id, {"revision": revision})
    except Exception as exc:
        logger.warning(
            "Load offline di %s@%s fallito (%s); tento fetch normale",
            model_id, revision, exc,
        )
        os.environ.pop("HF_HUB_OFFLINE", None)
        os.environ.pop("TRANSFORMERS_OFFLINE", None)
        try:
            pipe = _try_load(model_id, {"revision": revision})
        except Exception as exc2:
            logger.warning("Impossibile caricare il motore di riconoscimento: %s", exc2)
            return None

    return NeuralRecognizer(pipeline=pipe, threshold=threshold)
