# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Misura recall (fuga) e falsi positivi (FP) del riconoscimento
di nomi di persona, PRIMA e DOPO l'attivazione del dizionario nomi
italiani (FASE 2).

Corpora usati:
 1. Corpus dev — ``tests.corpus_annotato`` (76 frasi formali)
 2. Corpus onesto — ``benchmark.frasi_nuove`` (20 frasi inedite,
    stesso dominio formale)
 3. Corpus colloquiale — ``benchmark.frasi_colloquiali`` (30 frasi
    informali + 15 frasi trap senza persone).

Metrica per corpus:
 - fuga_pers   = 1 - recall_persona  (quanti nomi/cognomi persona non
                                       sono stati mascherati)
 - falsi_pos_% = FP / totale_output   (quante entità PERSONA emesse ma
                                        non presenti nel ground truth)

Modalità:
 - ``senza``   → PRIVACYBRIDGE_NO_NOMI_IT=1: recognizer nomi disabilitato.
 - ``con``     → default (attivo).

Uso:
    python -m benchmark.misura_dizionario > benchmark/misura_dizionario_output.txt
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


# ---------------------------------------------------------------------------
# Utility: recupera i "valori persona" attesi per ciascun corpus
# ---------------------------------------------------------------------------

def _spans_qualsiasi(entita: list[dict]) -> list[tuple[int, int]]:
    """Restituisce gli span [start,end) di TUTTE le entità annotate
    (qualunque tipo). Usato per distinguere FP puri (valore in testo
    libero) da riclassificazioni (valore dentro uno span annotato di
    altro tipo — es. ORG)."""
    return [(e["start"], e["end"]) for e in entita]


def _persone_da_corpus_annotato() -> Iterable[tuple[str, list[str], list[tuple[int,int]]]]:
    from tests.corpus_annotato import CORPUS
    for entry in CORPUS:
        testo = entry["testo"]
        val_persona = [
            testo[e["start"]:e["end"]]
            for e in entry["entita"]
            if e["tipo"] in {"PERSON", "PERSONA"}
        ]
        yield testo, val_persona, _spans_qualsiasi(entry["entita"])


def _persone_da_frasi_nuove() -> Iterable[tuple[str, list[str], list[tuple[int,int]]]]:
    from benchmark.frasi_nuove import FRASI_NUOVE
    for entry in FRASI_NUOVE:
        testo = entry["testo"]
        val_persona = [
            testo[e["start"]:e["end"]]
            for e in entry["entita"]
            if e["tipo"] == "PERSON"
        ]
        yield testo, val_persona, _spans_qualsiasi(entry["entita"])


def _persone_da_colloquiali() -> Iterable[tuple[str, list[str], list[tuple[int,int]]]]:
    from benchmark.frasi_colloquiali import (
        FRASI,
        FRASI_MINUSCOLO,
        FRASI_MINUSCOLO_TRAP,
        FRASI_TRAP,
    )
    for testo, ents in FRASI:
        yield testo, list(ents), []
    for testo, ents in FRASI_MINUSCOLO:
        yield testo, list(ents), []
    for testo in FRASI_TRAP:
        yield testo, [], []
    for testo in FRASI_MINUSCOLO_TRAP:
        yield testo, [], []


CORPORA = [
    ("corpus_dev (76 frasi formali)", _persone_da_corpus_annotato),
    ("corpus_nuove (20 frasi formali)", _persone_da_frasi_nuove),
    ("corpus_colloquiale (30 + 15 trap)", _persone_da_colloquiali),
]


# ---------------------------------------------------------------------------
# Misura su un corpus con l'analyzer in una modalità
# ---------------------------------------------------------------------------

DUMP_FP = os.environ.get("DUMP_FP") == "1"


def modo_str(senza: bool) -> str:
    return "senza" if senza else "con"


def _valuta(corpus_iter, senza_dizionario: bool) -> dict:
    # Toggle dizionario nomi italiani via env var.
    if senza_dizionario:
        os.environ["PRIVACYBRIDGE_NO_NOMI_IT"] = "1"
    else:
        os.environ.pop("PRIVACYBRIDGE_NO_NOMI_IT", None)

    # Ricostruisci analyzer per applicare la modalità.
    from backend.motore import anonimizza, reset_analyzer
    reset_analyzer()

    tot_attesi = 0
    tot_mascherati = 0
    tot_emessi_persona = 0
    tot_falsi_positivi_puri = 0
    tot_riclassificati = 0

    for i, (testo, attesi, spans_annotati) in enumerate(corpus_iter):
        sess = f"misura-{'senza' if senza_dizionario else 'con'}-{i}"
        try:
            out, ents = anonimizza(testo, sess)
        except Exception as exc:
            print(f"  ERRORE su frase {i}: {exc}", file=sys.stderr)
            continue

        tot_attesi += len(attesi)
        for a in attesi:
            if a not in out:
                tot_mascherati += 1
            else:
                if DUMP_FP:
                    print(
                        f"    NM[{modo_str(senza_dizionario)}] {a!r} "
                        f"in: {testo[:90]!r}",
                        file=sys.stderr,
                    )

        persona_ents = [
            e for e in ents
            if "PERSONA" in e["tipo"] and not e.get("suggerito")
        ]
        tot_emessi_persona += len(persona_ents)
        for e in persona_ents:
            v = e["valore_reale"]
            # Vero positivo se il valore emesso corrisponde a (o è
            # contenuto/contiene) una persona attesa.
            vero_pos = any((v == a or v in a or a in v) for a in attesi)
            if vero_pos:
                continue
            # RIclassificazione: il valore sta dentro uno span annotato
            # di tipo diverso (es. dentro un ORG). Non è un FP puro —
            # l'utente vedrà l'entità e potrà correggerne il tipo, ma il
            # valore è stato comunque anonimizzato.
            posizioni = [j for j in range(len(testo)) if testo[j:j+len(v)] == v]
            in_span_altro = any(
                any(s_start <= pos and pos + len(v) <= s_end for (s_start, s_end) in spans_annotati)
                for pos in posizioni
            )
            if in_span_altro:
                tot_riclassificati += 1
                if DUMP_FP:
                    print(
                        f"    RC[{modo_str(senza_dizionario)}] {v!r} in: {testo[:90]!r}",
                        file=sys.stderr,
                    )
            else:
                tot_falsi_positivi_puri += 1
                if DUMP_FP:
                    print(
                        f"    FP[{modo_str(senza_dizionario)}] {v!r} in: {testo[:90]!r}",
                        file=sys.stderr,
                    )

    fuga = (
        1.0 - (tot_mascherati / tot_attesi)
        if tot_attesi else 0.0
    )
    fp_pct_puri = (
        (tot_falsi_positivi_puri / tot_emessi_persona)
        if tot_emessi_persona else 0.0
    )
    return {
        "attesi": tot_attesi,
        "mascherati": tot_mascherati,
        "fuga_pct": fuga * 100.0,
        "emessi_persona": tot_emessi_persona,
        "fp_puri": tot_falsi_positivi_puri,
        "riclassificati": tot_riclassificati,
        "fp_pct_puri": fp_pct_puri * 100.0,
    }


def _stampa_riga(nome: str, res: dict) -> None:
    print(
        f"  {nome:15s}  "
        f"attesi={res['attesi']:4d}  "
        f"non_mascherati={res['attesi']-res['mascherati']:3d}  "
        f"fuga={res['fuga_pct']:5.1f}%   "
        f"emessi={res['emessi_persona']:4d}  "
        f"FP_puri={res['fp_puri']:3d}  "
        f"FP%={res['fp_pct_puri']:5.1f}%  "
        f"riclassificati={res['riclassificati']:3d}"
    )


def main() -> int:
    print("=" * 96)
    print("FASE 2 — Misura fuga + FP: PRIMA vs DOPO dizionario nomi italiani")
    print("=" * 96)

    for nome_corpus, factory in CORPORA:
        print(f"\n--- {nome_corpus} ---")
        risultati = {}
        for modo in ("senza", "con"):
            risultati[modo] = _valuta(factory(), senza_dizionario=(modo == "senza"))
        _stampa_riga("SENZA dizionario", risultati["senza"])
        _stampa_riga("CON  dizionario", risultati["con"])
        delta_fuga = risultati["con"]["fuga_pct"] - risultati["senza"]["fuga_pct"]
        delta_fp = risultati["con"]["fp_pct_puri"] - risultati["senza"]["fp_pct_puri"]
        segno = lambda x: "+" if x >= 0 else ""
        print(
            f"  delta:            "
            f"fuga={segno(delta_fuga)}{delta_fuga:.1f}pp   "
            f"FP%={segno(delta_fp)}{delta_fp:.1f}pp"
        )

    print("\n" + "=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
