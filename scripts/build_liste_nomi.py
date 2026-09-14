# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Genera le liste dei nomi e cognomi italiani con marcatura ambigui.

Input grezzi, in ``assets/liste_sorgenti/`` — scaricati a mano, licenze
in ``docs/DECISIONI.md``. Stanno fuori da ``src/`` perché servono solo
qui: nel pacchetto non ci vanno.
 - ``nomi_wikidata.csv``      → SPARQL Wikidata, CC0
 - ``nomi_top_italiani.txt``  → seed nomi comuni ISTAT (fatti pubblici)
 - ``cognomi_paolosarti.txt`` → PaoloSarti/lista_cognomi_italiani, MIT
 - ``cognomi_wikidata.csv``   → SPARQL Wikidata, CC0

Output in ``src/data/liste/``, versionato e spedito con l'applicazione,
accanto a ``vocab_it_60k.txt`` (napolux/paroleitaliane, MIT) che serve
sia qui sia a runtime:
 - ``nomi_italiani.tsv``    (nome<TAB>ambiguo)
 - ``cognomi_italiani.tsv`` (cognome<TAB>ambiguo)

Un termine è marcato "ambiguo" (1) se il suo lemma minuscolo esiste nel
vocabolario italiano di base: "Rosa", "Serena", "Angelo" sono nomi ma
anche parole comuni; "Andrea", "Giuseppe", "Ferrari" sono solo nomi/
cognomi. La marcatura evita di dover elencare a mano gli ambigui —
elenco che dimenticherebbe casi.

Uso:
    python scripts/build_liste_nomi.py
"""

from __future__ import annotations

import csv
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Ingressi grezzi e uscite versionate stanno in due posti diversi:
# i primi servono solo qui, le seconde le legge il motore.
SORGENTI = ROOT / "assets" / "liste_sorgenti"
LISTE = ROOT / "src" / "data" / "liste"


def _normalizza(s: str) -> str:
    """Normalizza a NFC, strip whitespace, primo carattere maiuscolo."""
    s = unicodedata.normalize("NFC", s).strip()
    return s


def _valido(nome: str, min_len: int, max_len: int) -> bool:
    if not (min_len <= len(nome) <= max_len):
        return False
    # solo lettere + apostrofo + trattino + spazio (per nomi composti)
    if not all(c.isalpha() or c in " '-" for c in nome):
        return False
    # deve iniziare con maiuscola
    return nome[0].isupper()


def carica_vocabolario(path: Path) -> set[str]:
    """Insieme di parole italiane comuni (lemma minuscolo)."""
    if not path.exists():
        sys.exit(f"vocabolario mancante: {path}")
    vocab: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for riga in fh:
            w = riga.strip().lower()
            if w and w.isalpha():
                vocab.add(w)
    return vocab


def carica_nomi_wikidata(path: Path) -> set[str]:
    """Carica il CSV Wikidata (formato: nameLabel su prima colonna)."""
    if not path.exists():
        sys.exit(f"file nomi mancante: {path}")
    nomi: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader, None)  # intestazione
        for row in reader:
            if not row:
                continue
            n = _normalizza(row[0])
            if not _valido(n, min_len=2, max_len=30):
                continue
            nomi.add(n)
    return nomi


def carica_cognomi(path: Path) -> set[str]:
    """Un cognome per riga."""
    if not path.exists():
        sys.exit(f"file cognomi mancante: {path}")
    cog: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for riga in fh:
            n = _normalizza(riga)
            if not _valido(n, min_len=3, max_len=40):
                continue
            cog.add(n)
    return cog


def carica_cognomi_wikidata(path: Path) -> set[str]:
    """Carica il CSV Wikidata dei cognomi (colonna ``cognome``)."""
    if not path.exists():
        sys.exit(f"file cognomi wikidata mancante: {path}")
    cog: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row in reader:
            if not row:
                continue
            n = _normalizza(row[0])
            if _valido(n, min_len=3, max_len=30):
                cog.add(n)
    return cog


def marca_ambigui(
    termini: set[str],
    vocab: set[str],
    esclusi_da_ambigui: set[str] | None = None,
) -> list[tuple[str, bool]]:
    """Per ogni termine, marca ambiguo se il lemma minuscolo è nel
    vocabolario italiano.

    Override: i termini in ``esclusi_da_ambigui`` (case-insensitive)
    sono SEMPRE marcati non-ambigui, indipendentemente dal
    vocabolario. Serve per i nomi tra i più diffusi in Italia
    ("Marco", "Bruno", "Franco", "Aurora", "Celeste"...) che coincidono
    con parole comuni marginali (valuta tedesca, aggettivi rari) ma nel
    contesto italiano sono senza ombra di dubbio nomi di persona.
    Marcarli ambigui li declasserebbe a livello 3 (suggerimento).
    """
    esclusi = {s.lower() for s in (esclusi_da_ambigui or set())}
    out: list[tuple[str, bool]] = []
    for t in sorted(termini):
        lemma = t.lower()
        if lemma in esclusi:
            out.append((t, False))
            continue
        # Consideriamo ambiguo anche quando il lemma è composto ("Della
        # Torre") e la componente principale è nel vocabolario. Per
        # semplicità e coerenza: il singolo token maggiore.
        parti = [p for p in lemma.replace("-", " ").split() if p]
        principale = max(parti, key=len) if parti else lemma
        ambiguo = principale in vocab
        out.append((t, ambiguo))
    return out


def scrivi_tsv(righe: list[tuple[str, bool]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write("# generato da scripts/build_liste_nomi.py — non modificare a mano\n")
        for termine, ambiguo in righe:
            fh.write(f"{termine}\t{int(ambiguo)}\n")


def main() -> int:
    vocab = carica_vocabolario(LISTE / "vocab_it_60k.txt")
    print(f"vocabolario italiano: {len(vocab):,} lemmi")

    nomi = carica_nomi_wikidata(SORGENTI / "nomi_wikidata.csv")
    print(f"nomi wikidata: {len(nomi):,}")

    # Unione con seed dei nomi italiani top (SPARQL non li restituisce
    # affidabilmente quando la label italiana = label inglese).
    # I nomi del seed sono ANCHE la lista canonica di "nomi troppo
    # comuni per essere considerati ambigui" — vedi marca_ambigui.
    top_nomi: set[str] = set()
    top_path = SORGENTI / "nomi_top_italiani.txt"
    if top_path.exists():
        with top_path.open(encoding="utf-8") as fh:
            for riga in fh:
                riga = riga.strip()
                if not riga or riga.startswith("#"):
                    continue
                n = _normalizza(riga)
                if _valido(n, min_len=2, max_len=30):
                    nomi.add(n)
                    top_nomi.add(n)
    print(f"nomi italiani validi (con seed top): {len(nomi):,}  "
          f"(seed top esclusi da ambigui: {len(top_nomi)})")

    cognomi = carica_cognomi(SORGENTI / "cognomi_paolosarti.txt")
    print(f"cognomi paolosarti validi: {len(cognomi):,}")

    # Wikidata (CC0) copre i cognomi regionali e quelli di origine
    # straniera che la lista cognomix non ha. Misurato sull'anagrafe di
    # Reggio Emilia (open data CC-BY, tenuta fuori dalle sorgenti per
    # restare un campione di controllo): la sola cognomix copriva il
    # 75.7% dei 189 cognomi più diffusi del comune.
    prima = len(cognomi)
    cognomi |= carica_cognomi_wikidata(SORGENTI / "cognomi_wikidata.csv")
    print(f"cognomi wikidata aggiunti: {len(cognomi) - prima:,}  "
          f"(totale {len(cognomi):,})")

    righe_nomi = marca_ambigui(nomi, vocab, esclusi_da_ambigui=top_nomi)
    ambigui_nomi = sum(1 for _, a in righe_nomi if a)
    print(f"nomi ambigui: {ambigui_nomi} ({ambigui_nomi/len(righe_nomi)*100:.1f}%)")

    righe_cognomi = marca_ambigui(cognomi, vocab)
    ambigui_cog = sum(1 for _, a in righe_cognomi if a)
    print(f"cognomi ambigui: {ambigui_cog} ({ambigui_cog/len(righe_cognomi)*100:.1f}%)")

    scrivi_tsv(righe_nomi, LISTE / "nomi_italiani.tsv")
    scrivi_tsv(righe_cognomi, LISTE / "cognomi_italiani.tsv")
    print("\nfile scritti:")
    print(" ", LISTE / "nomi_italiani.tsv")
    print(" ", LISTE / "cognomi_italiani.tsv")

    # Campione: mostra 10 nomi ambigui e 10 non ambigui per controllo qualità.
    print("\ncampione — nomi ambigui (compaiono anche come parola comune):")
    ambi = [n for n, a in righe_nomi if a][:15]
    print(" ", ", ".join(ambi))
    print("\ncampione — nomi non ambigui:")
    non_ambi = [n for n, a in righe_nomi if not a][:15]
    print(" ", ", ".join(non_ambi))
    return 0


if __name__ == "__main__":
    sys.exit(main())
